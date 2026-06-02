import json
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

# Configuration
# Paths are provided dynamically via function arguments or CLI
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
MAX_RESULTS = 5

def search_youtube(query, api_key, max_results=5):
    """
    Search YouTube for a specific query.
    Returns a list of video dictionaries.
    """
    if not api_key:
        print("Error: YOUTUBE_API_KEY not found in .env file.")
        return []

    print(f"Searching YouTube for: '{query}'...")
    
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'part': 'snippet',
        'q': query,
        'type': 'video',
        'key': api_key,
        'maxResults': max_results,
        'relevanceLanguage': 'en',
        'videoEmbeddable': 'true',  # Ensure we can embed/link it
        'safeSearch': 'moderate'    # Educational safety
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        videos = []
        for item in data.get('items', []):
            video_id = item['id']['videoId']
            snippet = item['snippet']
            
            video = {
                'title': snippet['title'],
                'description': snippet['description'],
                'thumbnail': snippet['thumbnails']['medium']['url'],
                'channel': snippet['channelTitle'],
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'embed_url': f"https://www.youtube.com/embed/{video_id}"
            }
            videos.append(video)
            
        return videos

    except requests.exceptions.HTTPError as e:
        print(f" YouTube API Error: {e}")
        return []
    except Exception as e:
        print(f" Unexpected Error: {e}")
        return []

def _parse_grade_subject(json_path):
    """
    Infer grade and subject from the folder path.
    Expected structure: .../Grade_X/Subject/json_output/file.json
    Returns (grade_label, subject) e.g. ("Grade 7", "Math")
    """
    parts = Path(json_path).resolve().parts
    grade_label = "General"
    subject = "Education"
    for i, part in enumerate(parts):
        if part.lower().startswith("grade_"):
            grade_label = part.replace("_", " ")
            if i + 1 < len(parts) and parts[i + 1].lower() != "json_output":
                subject = parts[i + 1]
            break
    return grade_label, subject

def get_videos_for_topic(json_path, topic_index=0):
    """
    Load a topic from JSON and fetch relevant videos.
    Grade and subject are inferred dynamically from the file path.
    """
    if not os.path.exists(json_path):
        print(f"File not found: {json_path}")
        return None, []

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if topic_index >= len(data):
        print(f" Topic index {topic_index} out of range.")
        return None, []

    topic = data[topic_index]
    topic_name = topic['topic_name']

    # Dynamically infer grade and subject from folder path
    grade_label, subject = _parse_grade_subject(json_path)

    # Construct a smart educational query using dynamic metadata
    query = f"{grade_label} {subject} {topic_name} explanation"

    videos = search_youtube(query, YOUTUBE_API_KEY, MAX_RESULTS)

    return topic_name, videos

def main(json_path, topic_index=0):
    print("="*60)
    print(" YouTube Educational Video Fetcher")
    print("="*60)

    result = get_videos_for_topic(json_path, topic_index)
    if result is None:
        return
    topic_name, videos = result

    if videos:
        print(f"\n Found {len(videos)} videos for '{topic_name}':\n")
        for i, vid in enumerate(videos, 1):
            print(f"{i}. {vid['title']}")
            print(f"    Channel: {vid['channel']}")
            print(f"    Link: {vid['url']}")
            print("-" * 40)

        # Save to a JSON file for other parts of the pipeline
        output = {
            "topic": topic_name,
            "videos": videos
        }
        with open("youtube_links.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        print("\nSaved links to 'youtube_links.json'")
    else:
        print("\n No videos found or API error.")

if __name__ == "__main__":
    # CLI usage: python get_youtube_links.py <path_to_json> [topic_index]
    from pathlib import Path
    if len(sys.argv) < 2:
        print("Usage: python get_youtube_links.py <path_to_json> [topic_index]")
        print("Example: python get_youtube_links.py generated_contents/user1/content/Grade_7/Math/json_output/chapter1.json 0")
        sys.exit(1)

    json_path = sys.argv[1]
    topic_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    main(json_path, topic_idx)
