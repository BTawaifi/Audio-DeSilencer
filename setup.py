from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as readme_file:
    long_description = readme_file.read()

setup(
    name="Audio-DeSilencer",
    version="1.0.3",
    description="An audio processing tool for detecting and separating silent and non-silent audio regions.",
    author="Boutros Tawaifi",
    author_email="boutrous.m.tawaifi@gmail.com",
    license="MIT",
    url="https://github.com/BTawaifi/Audio-DeSilencer",
    packages=find_packages(exclude=("tests", "tests.*")),
    python_requires=">=3.10",
    install_requires=[
        "pydub>=0.25.1",
        "audioop-lts>=0.2.2; python_version >= '3.13'",
    ],
    entry_points={
        "console_scripts": [
            "audio-desilencer=audio_desilencer.audio_processor:main",
        ],
    },
    keywords=["audio", "processing", "silence removal", "pause removal"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Operating System :: OS Independent",
    ],
    long_description=long_description,
    long_description_content_type="text/markdown",
)
