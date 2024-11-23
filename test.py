import streamlit as st
import cv2
import os
import tempfile
import torch
import requests

# YOLOv5 Object Detection
def detect_objects_yolov5(image_path, model, conf_thresh=0.6, iou_thresh=0.3):
    results = model(image_path)
    model.conf = conf_thresh
    model.iou = iou_thresh

    detected_objects = []
    for *box, conf, cls in results.xyxy[0]:  # x1, y1, x2, y2, confidence, class
        x1, y1, x2, y2 = map(int, box)
        detected_objects.append({
            "bbox": (x1, y1, x2, y2),
            "confidence": float(conf),
            "class": int(cls),
        })
    return detected_objects, results

# Crop and save object
def crop_and_save_object(image, bbox, output_dir, obj_index):
    x1, y1, x2, y2 = bbox
    cropped_img = image[y1:y2, x1:x2]
    output_path = os.path.join(output_dir, f"cropped_object_{obj_index}.png")
    cv2.imwrite(output_path, cropped_img)
    return output_path

# Imgur Upload
def upload_to_imgur(image_path, client_id):
    headers = {'Authorization': f'Client-ID {client_id}'}
    with open(image_path, 'rb') as img:
        response = requests.post("https://api.imgur.com/3/image", headers=headers, files={"image": img})
    data = response.json()
    if response.status_code == 200 and data["success"]:
        return data["data"]["link"]
    else:
        return None

# Video processing function
def process_video(video_path, model, frame_skip=30):
    cap = cv2.VideoCapture(video_path)
    frames = []
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_count % frame_skip == 0:
            temp_path = f"frame_{frame_count}.jpg"
            cv2.imwrite(temp_path, frame)
            frames.append({"path": temp_path, "frame": frame})
        frame_count += 1

    cap.release()
    return frames

# Main Streamlit application
def main():
    st.title("Object Detection in Videos")
    st.write("Upload a video to detect objects and search for items using Google Lens.")

    # Inputs
    # imgur_client_id = st.text_input("Imgur Client ID:", type="password")
    # api_key = st.text_input("SerpApi API Key:", type="password")

    api_key = "d391abaa4565995bf471c54bb1644750e3f874ae0c8f59a48dfb9ae7e590cc7e"
    imgur_client_id = "2f2e44e79e1f7fb"

    uploaded_file = st.file_uploader("Upload a video", type=["mp4", "avi", "mov", "mkv"])
    if uploaded_file:
        temp_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
        with open(temp_video_path, "wb") as temp_file:
            temp_file.write(uploaded_file.read())

        st.video(temp_video_path)
        st.write("Processing video...")

        # Load YOLOv5 model
        model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True)

        # Process video
        frames = process_video(temp_video_path, model, frame_skip=30)
        st.write(f"Extracted {len(frames)} frames for analysis.")

        selected_frame = st.selectbox("Select a frame to analyze", options=range(len(frames)))
        frame_data = frames[selected_frame]
        st.image(frame_data["path"], caption=f"Frame {selected_frame}")

        # Detect objects in the selected frame
        with st.spinner("Detecting objects..."):
            detected_objects, _ = detect_objects_yolov5(frame_data["path"], model)

        if detected_objects:
            st.write(f"Detected {len(detected_objects)} objects:")
            selected_objects = st.multiselect(
                "Select objects to search",
                options=range(len(detected_objects)),
                format_func=lambda x: f"Object {x + 1} (Class: {model.names[detected_objects[x]['class']]})"
            )

            for obj_index in selected_objects:
                obj = detected_objects[obj_index]
                bbox = obj["bbox"]
                cropped_path = crop_and_save_object(frame_data["frame"], bbox, tempfile.gettempdir(), obj_index)
                st.image(cropped_path, caption=f"Cropped Object {obj_index + 1}")

                # Upload to Imgur
                image_url = upload_to_imgur(cropped_path, imgur_client_id)
                if image_url:
                    st.write(f"Image uploaded: {image_url}")

                    # Perform Google Lens Search
                    st.write("Searching for similar items...")
                    params = {
                        "engine": "google_lens",
                        "country": "in",
                        "url": image_url,
                        "api_key": api_key,
                    }

                    response = requests.get("https://serpapi.com/search", params=params)
                    results = response.json()

                    if "visual_matches" in results:
                        st.write(f"Results for Object {obj_index + 1}:")
                        for match in results["visual_matches"][:5]:  # Limit to 5 results
                            title = match.get("title", "No title")
                            link = match.get("link", "No link")
                            if "www.amazon" in link or "www.flipkart" in link:
                                with st.container():
                                    st.markdown(f"**{title}**")
                                    st.write(f"[BUY]({link})")
                            st.write(f"[{match.get('title', 'No title')}]({match.get('link')})")
                    else:
                        st.error("No visual matches found.")
                else:
                    st.error("Failed to upload image to Imgur.")
        else:
            st.warning("No objects detected in the selected frame.")

if __name__ == "__main__":
    main()
