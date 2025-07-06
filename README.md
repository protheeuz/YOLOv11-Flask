## YOLOv11 - Flask
Object Detection Web App using YOLOv11 and Flask. Supports RTSP Streams and Video Uploads. A study case for a Fall Detection System for the Elderly.
----------------------------------------------------------------

## Features
**1. User Authentication:**
+ Secure login and registration functionality using Flask-Login.
+ Supports session management for user access.

**2. Object Detection:**
+ Utilitizes YOLOv11 for *real-time object detection*.
+ Allows video uploads for processing.
+ Provides RTSP stream integration for live detection.

**3. File Management:**
+ Uploaded videos and detected frames are stored in a structured directory.
+ Automatically cleanup of old detection files to maintain storage efficiency.

**4. Real-Time Notifications:**
+ Displays the count of new logins since the current day for authenticated users.

**5. Cross-Origin Resource Sharing (CORS):**
+ Configured to allow specific resources to be accessed from external domains.

## Installation
**1. Clone the repository:**
```git clone https://github.com/protheeuz/YOLOv11-Flask.git```
**2. Install dependencies:**
```pip install -r requirements.txt```
**3. Create and configure a .env file:**
+ Define environment variables such as database credentials, Flask secret key, and other required settings.
**4. Initialize the database:**
+ Execute the necessary SQL scripts or ORM migrations to set up the database schema.
**5. Run the application:**
```python app.py```
**6. Access the web app:**
+ Open your browser and navigate to ``http://localhost:PORT``.

----------------------------------------------------------------

## Directory Structure
```
.
├── config.py            # Configuration for Flask and other services
├── database.py          # Database connection and teardown handlers
├── detection.py         # Cleanup and detection-specific logic
├── models.py            # Database models and user-related operations
├── views/
│   ├── auth.py          # Routes for authentication
│   ├── main.py          # Main application routes
├── static/
│   ├── uploads/         # Uploaded videos and detection files
├── templates/           # HTML templates for the Flask app
├── main.py              # Entry point for the Flask app
├── requirements.txt     # Python dependencies
├── auth_bp.py           # Authentication logic and routes
├── additional_logic.py  # Auxiliary functions and custom features
└── rtsp_handler.py      # RTSP streaming and fall detection logic
```

----------------------------------------------------------------

## Configuration
+ UPLOAD_FOLDER: Path to the directory where uloaded files are stored.
+ DETECTION_IMAGES_FOLDER: Path to the directory for detection result images.
+ PUBLIC_URL: Publicly accessible URL for the application.
+ ALLOWED_EXTENSIONS: Set of allowed file extensions for upload.
+ CONFIDENCE_THRESHOLD: Confidence threshold for object detection labels.

----------------------------------------------------------------
## Cleanup Task
A background thread is implemented to periodically clean up old detection files. The task runs every 30 seconds to ensure storage is managed efficiently.

----------------------------------------------------------------
## Usage
**1. Login:**
+ Create an account or log in using your credentials.
**2. Upload Video:**
+ Navigate to the upload page and upload a video file.
**3. Real-Time Detection:**
+ Monitor object detection output directly on the application.
**4. RTSP Stream Monitoring:**
+ Add RTSP stream URLs for live monitoring and fall detection.
