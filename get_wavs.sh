# script to generate wav files from file formats that MacWhisper is less versatile with
# MacWhisper says AAC works, so let's leave that out for now

IFS=$'\n'
for ext in avi mp2 mpg ogg wmv mkv ac3; do
    count=$(ls | grep -ie "${ext}$" | wc -l | awk '{print $1}')
    if [ "$count" = 0 ]; then
        echo "no $ext files, continuing..."
        continue
    fi
    for f in $(ls | grep -ie ${ext}$); do
        output="${f%.$ext}.wav"
        if [ ! -e "$output" ]; then
            echo "running ffmpeg on $f"
            ffmpeg -hide_banner -loglevel error -i "$f" "$output"
        fi
    done
done
