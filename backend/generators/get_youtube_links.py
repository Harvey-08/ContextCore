import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# Configuration
# You can change this to any JSON file you want to process
JSON_PATH = "class7/json_output/gegp105.json"
TOPIC_INDEX = 0  # First topic: Parallel and Intersecting Lines
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

def get_videos_for_topic(json_path, topic_index):
    """
    Load a topic from JSON and fetch relevant videos.
    """
    if not os.path.exists(json_path):
        print(f"File not found: {json_path}")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if topic_index >= len(data):
        print(f" Topic index {topic_index} out of range.")
        return

    topic = data[topic_index]
    topic_name = topic['topic_name']
    
    # Construct a smart educational query
    # "Class 7 Math Parallel and Intersecting Lines explanation"
    query = f"Class 7 Math {topic_name} explanation"
    
    videos = search_youtube(query, YOUTUBE_API_KEY, MAX_RESULTS)
    
    return topic_name, videos

def main():
    print("="*60)
    print(" YouTube Educational Video Fetcher")
    print("="*60)
    
    topic_name, videos = get_videos_for_topic(JSON_PATH, TOPIC_INDEX)
    
    if videos:
        print(f"\n Found {len(videos)} videos for '{topic_name}':\n")
        for i, vid in enumerate(videos, 1):
            print(f"{i}. {vid['title']}")
            print(f"    Channel: {vid['channel']}")
            print(f"    Link: {vid['url']}")
            print("-" * 40)
            
        # Optional: Save to a JSON file for other parts of your pipeline
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
    main()
