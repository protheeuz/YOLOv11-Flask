## detection.py
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

def save_detection_to_db(user_id, label, confidence):
    if label.lower() == "jatuh": 
        connection = get_db()
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO detections (user_id, label, confidence)
            VALUES (%s, %s, %s)
        """, (user_id, label, confidence))
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
                
                # Simpan ke database jika label adalah 'jatuh'
                save_detection_to_db(user_id, label, confidence)

                # Gambar bounding box dan label pada frame
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"{label} ({confidence:.2f})", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    return frame

def process_video(input_path, output_path, user_id):
    """
    Proses video yang diunggah untuk mendeteksi objek.
    """
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise ValueError(f"Tidak dapat membuka video input: {input_path}")

    # Konfigurasi output video
    fourcc = cv2.VideoWriter_fourcc(*'avc1') 
    fps = int(cap.get(cv2.CAP_PROP_FPS) or 25) 
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    frame_count = 0
    connection = get_db()
    cursor = connection.cursor()

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        try:
            # Jalankan deteksi pada frame
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

                        # Simpan ke database jika label adalah 'jatuh'
                        if label.lower() == "jatuh":
                            cropped_image = frame[y1:y2, x1:x2]
                            image_filename = f"fall_{user_id}_{int(time.time())}_{frame_count}.jpg"
                            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_filename)
                            cv2.imwrite(image_path, cropped_image)

                            cursor.execute("""
                                INSERT INTO detections (user_id, label, confidence, image_path)
                                VALUES (%s, %s, %s, %s)
                            """, (user_id, label, confidence, image_path))

                        # Gambar bounding box dan label pada frame
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(frame, f"{label} ({confidence:.2f})", (x1, y1 - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Tulis frame yang telah diproses ke video keluaran
            out.write(frame)
        except Exception as e:
            print(f"Kesalahan saat memproses frame {frame_count}: {e}")
            continue

    connection.commit()
    cursor.close()
    cap.release()
    out.release()
    print(f"Video output disimpan ke: {output_path}")

def run_realtime_detection(user_id, rtsp_url=None, video_file=None):
    input_source = rtsp_url if rtsp_url else video_file
    cap = cv2.VideoCapture(input_source)
    if not cap.isOpened():
        raise ValueError(f"Tidak dapat membuka video atau RTSP: {input_source}")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        try:
            frame = detect_and_label(frame, user_id)
            cv2.imshow("Fall Detection Realtime", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        except Exception as e:
            print(f"Kesalahan saat deteksi realtime: {e}")
            break
    cap.release()
    cv2.destroyAllWindows()