import os
import cv2
from ultralytics import YOLO
from flask import current_app
from database import get_db
import time

# Load YOLO model
model_path = "models/yolov11/fall-detection-model.pt" 
model = YOLO(model_path)

# Mapping label untuk penggantian nama kelas (pastikan sesuai urutan RoboFlow)
LABEL_MAP = {
    0: "Jatuh",  # Mengganti kelas dengan indeks 0 menjadi "Jatuh"
    1: "Normal"  # Mengganti kelas dengan indeks 1 menjadi "Normal"
}

CONFIDENCE_THRESHOLD = 0.7

def generate_frames(video_source, user_id):
    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        raise ValueError(f"Tidak dapat membuka video atau URL RTSP: {video_source}")
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        try:
            frame = detect_and_label(frame, user_id)
            # Encode frame ke format JPEG
            _, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        except Exception as e:
            print(f"Kesalahan saat memproses frame: {e}")
            break
    cap.release()

def save_frame_with_bbox(frame, frame_count, user_id):
    """
    Menyimpan frame full dengan bounding box untuk laporan email.
    """
    try:
        timestamp = int(time.time())
        image_filename = f"fall_{user_id}_{timestamp}_{frame_count}_bbox.jpg"
        
        abs_image_path = os.path.join(current_app.config['DETECTION_IMAGES_FOLDER'], image_filename)
        rel_image_path = f"uploads/detections/{image_filename}"
        
        os.makedirs(os.path.dirname(abs_image_path), exist_ok=True)
        
        success = cv2.imwrite(abs_image_path, frame)
        if not success:
            raise Exception("Failed to save image")
            
        print(f"Frame saved successfully to: {abs_image_path}")
        
        return rel_image_path
        
    except Exception as e:
        print(f"Error saving frame: {str(e)}")
        return None

def save_detection_to_db(user_id, label, confidence, image_path=None):
    """
    Menyimpan data deteksi ke database.
    """
    if label.lower() == "jatuh":
        connection = get_db()
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO detections (user_id, label, confidence, image_path)
            VALUES (%s, %s, %s, %s)
        """, (user_id, label, confidence, image_path))
        connection.commit()
        cursor.close()

def detect_and_label(frame, user_id):
    results = model(frame)
    for result in results:
        if hasattr(result, "boxes"):
            for box in result.boxes:
                # Ambil bounding box dan informasi deteksi
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                confidence = box.conf[0].item()
                class_id = int(box.cls[0].item())

                if confidence < CONFIDENCE_THRESHOLD:
                    continue  # Abaikan deteksi dengan confidence rendah
                
                # Ambil nama label berdasarkan indeks
                label = LABEL_MAP.get(class_id, f"Unknown-{class_id}")
                
                # Simpan ke database
                save_detection_to_db(user_id, label, confidence)

                # Gambar bounding box dan label pada frame
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"{label} ({confidence:.2f})", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    return frame

def process_video(input_path, output_path, user_id, save_for_email=False):
    """
    Proses video yang diunggah untuk mendeteksi objek.
    """
    try:
        # Buka video input
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise ValueError(f"Tidak dapat membuka video input: {input_path}")

        # Dapatkan properti video
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        if fps <= 0:
            fps = 25  # Default fps
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Normalize output path to use forward slashes
        output_path = output_path.replace('\\', '/')
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Use XVID codec instead of H264
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        temp_output = output_path.replace('.mp4', '.avi')
            
        # Create video writer
        out = cv2.VideoWriter(temp_output, fourcc, fps, (width, height))
        if not out.isOpened():
            raise ValueError(f"Tidak dapat membuat video output: {temp_output}")
        
        # Process frames...
        frame_count = 0
        highest_confidence = 0.0
        email_frame_path = None

        print(f"Mulai memproses video: {input_path}")
        print(f"Output sementara akan disimpan ke: {temp_output}")

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            try:
                # Your existing detection code here...
                results = model(frame)
                for result in results:
                    if hasattr(result, "boxes"):
                        for box in result.boxes:
                            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                            confidence = box.conf[0].item()
                            class_id = int(box.cls[0].item())

                            if confidence <= CONFIDENCE_THRESHOLD:
                                continue 

                            label = LABEL_MAP.get(class_id, f"Unknown-{class_id}")
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            cv2.putText(frame, f"{label} ({confidence:.2f})", 
                                      (x1, y1 - 10),
                                      cv2.FONT_HERSHEY_SIMPLEX, 
                                      0.5, 
                                      (0, 255, 0), 
                                      2)

                            if label.lower() == "jatuh":
                                timestamp = int(time.time())
                                cropped_filename = f"fall_{user_id}_{timestamp}_{frame_count}.jpg"
                                rel_path = f"uploads/detections/{cropped_filename}"
                                abs_path = os.path.join(current_app.config['DETECTION_IMAGES_FOLDER'], cropped_filename)
                                
                                # Save cropped image
                                cropped_image = frame[y1:y2, x1:x2]
                                cv2.imwrite(abs_path, cropped_image)
                                save_detection_to_db(user_id, label, confidence, rel_path)

                                if confidence > highest_confidence and save_for_email:
                                    highest_confidence = confidence
                                    email_frame_path = save_frame_with_bbox(frame, frame_count, user_id)

                # Write the processed frame
                out.write(frame)

            except Exception as e:
                print(f"Error pada frame {frame_count}: {str(e)}")
                continue

        # Cleanup
        cap.release()
        out.release()
        cv2.destroyAllWindows()

        # Convert AVI to MP4 using FFmpeg
        try:
            import ffmpeg
            
            # Input AVI file
            stream = ffmpeg.input(temp_output)
            
            # Output MP4 file
            stream = ffmpeg.output(stream, output_path, vcodec='libx264', acodec='aac')
            
            # Run FFmpeg
            ffmpeg.run(stream, overwrite_output=True)
            
            # Remove temporary AVI file
            os.remove(temp_output)
            
            print(f"Video berhasil dikonversi ke MP4: {output_path}")
            
        except Exception as e:
            print(f"Gagal mengkonversi video ke MP4: {str(e)}")
            os.rename(temp_output, output_path)

        return email_frame_path

    except Exception as e:
        print(f"Error fatal saat memproses video: {str(e)}")
        raise