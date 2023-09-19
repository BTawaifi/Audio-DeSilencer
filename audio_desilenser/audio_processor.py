from pydub import AudioSegment
from pydub.silence import detect_nonsilent

try:
    # Load the audio file
    input_file_path = 'E:/interview.mp3'
    timeline_file_path = 'E:/audio_timelines.txt'  # Path to the timeline file for audio segments
    output_silent_path = 'E:/interview_silent.mp3'  # Path for the audio file containing silent parts
    output_non_silent_path = 'E:/interview_non_silent.mp3'  # Path for the audio file containing non-silent parts
    silent_txt_path = 'E:/silent_parts.txt'  # Path for the text file containing silent parts
    non_silent_txt_path = 'E:/non_silent_parts.txt'  # Path for the text file containing non-silent parts

    audio = AudioSegment.from_file(input_file_path, format="mp3")

    # Calculate the average amplitude of the audio
    average_amplitude = audio.dBFS

    # Set a threshold relative to the average amplitude (e.g., -30 dBFS below average)
    silence_thresh = average_amplitude - 30  # You can adjust this value as needed

    # Detect non-silent parts of the audio using the calculated threshold
    non_silent_parts = detect_nonsilent(audio, min_silence_len=100, silence_thresh=silence_thresh)

    # Create an empty list to store the audio timelines (both silent and non-silent)
    audio_timelines = []

    # Create audio segments for silent and non-silent parts
    audio_silent = AudioSegment.empty()
    audio_non_silent = AudioSegment.empty()

    # Create lists to store the start and end times of silent and non-silent parts
    silent_parts_times = []
    non_silent_parts_times = []

    # Iterate through the non-silent parts and calculate the timelines
    for i in range(len(non_silent_parts)):
        # Calculate the start and end times of each part
        start_time = non_silent_parts[i][0]
        end_time = non_silent_parts[i][1]

        # Append the start and end times to the audio_timelines list
        audio_timelines.append((start_time, end_time))

        # Append the non-silent part to the audio with non-silent parts
        audio_non_silent += audio[start_time:end_time]

        # Append the start and end times to the non-silent parts times list
        non_silent_parts_times.append((start_time, end_time))

        # Append the silent part to the audio with silent parts
        if i == 0:
            silent_start_time = 0
        else:
            silent_start_time = non_silent_parts[i - 1][1]
        silent_end_time = start_time

        # Append the start and end times to the silent parts times list
        silent_parts_times.append((silent_start_time, silent_end_time))

        audio_silent += audio[silent_start_time:silent_end_time]

    # ...

    # Write the silent parts times as an array of arrays to a text file
    with open(silent_txt_path, 'w') as silent_file:
        silent_data = [[start, end] for start, end in silent_parts_times]
        silent_file.write(str(silent_data))

    # Write the non-silent parts times as an array of arrays to a text file
    with open(non_silent_txt_path, 'w') as non_silent_file:
        non_silent_data = [[start, end] for start, end in non_silent_parts_times]
        non_silent_file.write(str(non_silent_data))

    # ...

    # Save the audio with silent parts to a file
    audio_silent.export(output_silent_path, format="mp3")

    # Save the audio with non-silent parts to a file
    audio_non_silent.export(output_non_silent_path, format="mp3")

    # Write the silent parts times to a text file
    with open(silent_txt_path, 'w') as silent_file:
        for start, end in silent_parts_times:
            silent_file.write(f"Start: {start} ms, End: {end} ms\n")

    # Write the non-silent parts times to a text file
    with open(non_silent_txt_path, 'w') as non_silent_file:
        for start, end in non_silent_parts_times:
            non_silent_file.write(f"Start: {start} ms, End: {end} ms\n")

    print("Audio timelines saved to:", timeline_file_path)
    print("Audio with silent parts saved to:", output_silent_path)
    print("Audio with non-silent parts saved to:", output_non_silent_path)
    print("Silent parts timeline saved to:", silent_txt_path)
    print("Non-silent parts timeline saved to:", non_silent_txt_path)

except Exception as e:
    print("An error occurred:", str(e))
