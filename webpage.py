def make_video(source_url):
    return f"""
<html>
    <head>
        <title>Traffic Camera Stream</title>
        <link href="https://vjs.zencdn.net/7.2.3/video-js.css" rel="stylesheet">
    </head>
    <body>
        <video id="stream-player" class="video-js vjs-default-skin" controls>
            <source src="{source_url}" type="application/x-mpegURL">
        </video>

        <script src="https://cdnjs.cloudflare.com/ajax/libs/videojs-contrib-hls/5.14.1/videojs-contrib-hls.js"></script>
        <script src="https://vjs.zencdn.net/7.2.3/video.js"></script>
        <script>
            var player = videojs('stream-player', {{width: 1280, height: 720, controls: true}});
            player.ready(function() {{
                player.autoplay('muted');
            }});
        </script>
    </body>
</html>
"""