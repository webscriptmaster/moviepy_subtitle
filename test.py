import logging
from pathlib import Path
from typing import List, Dict
import os
import subprocess
import json
import pysrt
import shutil
from moviepy.editor import (
    AudioFileClip, ColorClip, CompositeVideoClip, concatenate_videoclips,
    TextClip, VideoFileClip
)
from logging import info, error, debug
from moviepy.video.fx.crop import crop
from moviepy.video.fx.loop import loop

# Initialization
logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.DEBUG)

# Set the path to the ImageMagick executable
os.environ['IMAGEMAGICK_BINARY'] = '/usr/bin/convert'


def load_video_from_file(file: Path) -> VideoFileClip:
    if not file.exists():
        raise FileNotFoundError(f"Video file not found: {file}")
    return VideoFileClip(file.as_posix())


def crop_to_aspect_ratio(video: VideoFileClip, desired_aspect_ratio: float) -> VideoFileClip:
    video_aspect_ratio = video.w / video.h
    if video_aspect_ratio > desired_aspect_ratio:
        new_width = int(desired_aspect_ratio * video.h)
        new_height = video.h
        x1 = (video.w - new_width) // 2
        y1 = 0
    else:
        new_width = video.w
        new_height = int(video.w / desired_aspect_ratio)
        x1 = 0
        y1 = (video.h - new_height) // 2
    x2 = x1 + new_width
    y2 = y1 + new_height
    return crop(video, x1=x1, y1=y1, x2=x2, y2=y2)


def load_subtitles_from_file(srt_file: Path) -> pysrt.SubRipFile:
    if not srt_file.exists():
        raise FileNotFoundError(f"SRT File not found: {srt_file}")
    return pysrt.open(srt_file)


def adjust_segment_duration(segment: VideoFileClip, duration: float) -> VideoFileClip:
    current_duration = segment.duration
    if current_duration < duration:
        return loop(segment, duration=duration)
    elif current_duration > duration:
        return segment.subclip(0, duration)
    return segment


def adjust_segment_properties(segment: VideoFileClip, original: VideoFileClip) -> VideoFileClip:
    segment = segment.set_fps(original.fps)
    segment = segment.set_duration(segment.duration)
    segment = segment.resize(newsize=(original.w, original.h))
    return segment


def subriptime_to_seconds(srt_time: pysrt.SubRipTime) -> float:
    return srt_time.hours * 3600 + srt_time.minutes * 60 + srt_time.seconds + srt_time.milliseconds / 1000.0


def get_segments_using_srt(video: VideoFileClip, subtitles: pysrt.SubRipFile) -> (List[VideoFileClip], List[pysrt.SubRipItem]):
    subtitle_segments = []
    video_segments = []
    for subtitle in subtitles:
        start = subriptime_to_seconds(subtitle.start)
        end = subriptime_to_seconds(subtitle.end)
        video_segment = video.subclip(start, end)
        subtitle_segments.append(subtitle)
        video_segments.append(video_segment)
    return video_segments, subtitle_segments


def add_subtitles_to_clip(clip: VideoFileClip, subtitle: pysrt.SubRipItem, font_size: int = 33, color: str = "white", margin: int = 20) -> VideoFileClip:
    logging.info(f"Adding subtitle: {subtitle.text}")
    subtitle_clip = TextClip(
        subtitle.text,
        fontsize=font_size,
        color=color,
        stroke_color="white",
        stroke_width=1,
        font="Montserrat-SemiBold",
        method='caption',
        align='center',
        size=(clip.w - 2 * margin, None)
    ).set_duration(subriptime_to_seconds(subtitle.end) - subriptime_to_seconds(subtitle.start))
    text_width, text_height = subtitle_clip.size
    box_width = clip.w - 2 * margin
    box_height = text_height + margin
    box_clip = ColorClip(size=(box_width, box_height), color=(0, 0, 0)).set_opacity(0.7).set_duration(subtitle_clip.duration)
    box_position = ('center', clip.h - box_height - margin)
    subtitle_position = ('center', clip.h - box_height - margin + (box_height - text_height) / 2)
    box_clip = box_clip.set_position(box_position)
    subtitle_clip = subtitle_clip.set_position(subtitle_position)
    return CompositeVideoClip([clip, box_clip, subtitle_clip])


def replace_video_segments(
    original_segments: List[VideoFileClip],
    replacement_videos: Dict[int, VideoFileClip],
    subtitles: pysrt.SubRipFile,
    original_video: VideoFileClip
) -> List[VideoFileClip]:
    combined_segments = original_segments.copy()
    for replace_index, replacement_video in replacement_videos.items():
        if 0 <= replace_index < len(combined_segments):
            target_duration = combined_segments[replace_index].duration
            start = subriptime_to_seconds(subtitles[replace_index].start)
            end = subriptime_to_seconds(subtitles[replace_index].end)
            if start >= replacement_video.duration:
                error(f"Start time ({start}) is beyond the replacement video's duration ({replacement_video.duration}).")
            else:
                if end > replacement_video.duration:
                    end = replacement_video.duration
                replacement_segment = replacement_video.subclip(start, end)
                replacement_segment = adjust_segment_duration(replacement_segment, target_duration)
                adjusted_segment = adjust_segment_properties(replacement_segment, original_video)
                adjusted_segment_with_subtitles = add_subtitles_to_clip(adjusted_segment, subtitles[replace_index])
                combined_segments[replace_index] = adjusted_segment_with_subtitles
    return combined_segments


def generate_srt_from_txt_and_audio(txt_file: Path, audio_file: Path, output_folder: Path) -> Path:
    output_file_path = txt_file.with_name(txt_file.stem + "_aligned.json")
    command = f'python3.10 -m aeneas.tools.execute_task "{audio_file}" "{txt_file}" "task_language=eng|is_text_type=plain|os_task_file_format=json" "{output_file_path}"'
    logging.info(f"Running command: {command}")
    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    logging.info(f"Command output: {result.stdout.decode('utf-8')}")
    logging.error(f"Command error: {result.stderr.decode('utf-8')}")

    if not output_file_path.exists():
        raise FileNotFoundError(f"The output file {output_file_path} was not created. Check the command output above for errors.")

    with open(output_file_path, 'r') as f:
        sync_map = json.load(f)

    def convert_time(seconds):
        milliseconds = int((seconds - int(seconds)) * 1000)
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

    aligned_output = []
    for index, fragment in enumerate(sync_map['fragments']):
        start = convert_time(float(fragment['begin']))
        end = convert_time(float(fragment['end']))
        text = fragment['lines'][0].strip()
        aligned_output.append(f"{index + 1}\n{start} --> {end}\n{text}\n")

    srt_file = txt_file.with_name(txt_file.stem + "_with_timestamps.srt")
    with open(srt_file, 'w') as file:
        for line in aligned_output:
            file.write(line + "\n")

    return srt_file


def main(video_clips_path, my_video, mp3_file_of_same_video, txt_file_of_same_video, output_folder):
    input_video_file = Path(my_video)
    replacement_base_folder = Path(video_clips_path)

    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    # Generate SRT file from TXT and MP3
    srt_file = generate_srt_from_txt_and_audio(Path(txt_file_of_same_video), Path(mp3_file_of_same_video), output_folder)
    logging.info("Generated SRT file from TXT and MP3")

    video = load_video_from_file(input_video_file)
    logging.info("Video loaded successfully")
    cropped_video = crop_to_aspect_ratio(video, 4 / 5)
    logging.info("Video cropped to desired aspect ratio")
    subtitles = load_subtitles_from_file(srt_file)
    logging.info("Loaded SRT Subtitles from the provided subtitle file")
    video_segments, subtitle_segments = get_segments_using_srt(video, subtitles)
    logging.info("Segmented Input video based on the SRT Subtitles generated for it")
    output_video_segments = []
    start = 0
    for video_segment, new_subtitle_segment in zip(video_segments, subtitles):
        end = subriptime_to_seconds(new_subtitle_segment.end)
        required_duration = end - start
        new_video_segment = adjust_segment_duration(video_segment, required_duration)
        output_video_segments.append(new_video_segment.without_audio())
        start = end

    replacement_videos_per_combination = []

    for folder in replacement_base_folder.iterdir():
        if not folder.is_dir():
            continue

        folder_name = folder.name
        if not folder_name.isdigit():
            logging.warning(f"Folder name {folder_name} is not a valid segment index. Skipping...")
            continue

        replace_index = int(folder_name) - 1
        replacement_video_files = list(folder.glob("*.mp4"))
        logging.info(f"Found {len(replacement_video_files)} replacement video files in {folder}")

        for replacement_video_file in replacement_video_files:
            replacement_video = load_video_from_file(replacement_video_file)
            cropped_replacement_video = crop_to_aspect_ratio(replacement_video, 4 / 5)
            logging.info(f"Replacement video {replacement_video_file} cropped to desired aspect ratio")
            if len(replacement_videos_per_combination) < len(replacement_video_files):
                replacement_videos_per_combination.append({})
            replacement_videos_per_combination[replacement_video_files.index(replacement_video_file)][replace_index] = cropped_replacement_video

    for i, replacement_videos in enumerate(replacement_videos_per_combination):
        final_video_segments = replace_video_segments(
            output_video_segments, replacement_videos, subtitles, video
        )
        concatenated_video = concatenate_videoclips(final_video_segments)
        original_audio = video.audio.subclip(0, concatenated_video.duration)
        final_video_with_audio = concatenated_video.set_audio(original_audio)
        #tmp_path = Path('tmp')
        output_file = output_folder / f"output_variation_{i+1}.mp4"
        final_video_with_audio.write_videofile(output_file.as_posix(), codec="libx264", audio_codec="aac")
        #shutil.move(tmp_path, output_file)
        logging.info(f"Generated output video: {output_file}")


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Process video files")
    parser.add_argument("--input_clips", "-ic", required=True, help="Input clips directory")
    parser.add_argument("--input_video", "-iv", required=True, help="Input video file")
    parser.add_argument("--input_mp3", "-im", required=True, help="Input mp3 file")
    parser.add_argument("--input_txt", "-it", required=True, help="Input txt file")
    parser.add_argument("--output_dir", "-o", required=True, help="Output directory")

    args = parser.parse_args()
    main(args.input_clips, args.input_video, args.input_mp3, args.input_txt, Path(args.output_dir))

