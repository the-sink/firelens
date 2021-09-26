import webpage
import requests
import sys
import webbrowser

# Warning: this will spam your browser with video streams if you're not careful, it doesn't condense multiple into one page just yet
# To use: py stream_viewer.py <incident number>

# Will use the api to find nearby traffic cameras and display them in your browser as video streams (or in the case of wsdot, images)
# This is just an experiment! It's not a part of the actual api.

nearest_cameras = requests.get(f"http://127.0.0.1:8000/incident/{sys.argv[1]}/cameras").json()

if 'error' in nearest_cameras:
    print("No nearby cameras are available for that incident. Stopping...")
else:
    for camera in nearest_cameras:
        if camera['Type'] == 'sdot':
            stream = camera['ImageUrl'].replace('.jpg', '.stream')
            stream_url = f"https://58cc2dce193dd.streamlock.net:443/live/{stream}/playlist.m3u8"
            page_content = webpage.make_video(stream_url)
            file = open('video.html', 'w')
            file.write(page_content)
            file.close()
            webbrowser.open('video.html')
        elif camera['Type'] == 'wsdot':
            image_url = 'https://images.wsdot.wa.gov/nw/' + camera['ImageUrl']
            webbrowser.open(image_url)