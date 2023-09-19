from setuptools import setup, find_packages

setup(
    name='AudioDeSilencer',
    version='1.0',
    description='An audio processing tool for detecting and removing silence in audio recordings.',
    author='Boutros Tawaifi',
    author_email='boutrous.m.tawaifi@gmail.com',
    url='https://github.com/BTawaifi/AudioDeSilencer',
    packages=find_packages(),
    install_requires=[
        'pydub',
        'argparse',
    ],
    entry_points={
        'console_scripts': [
            'audio_desilencer=audio_desilencer.audio_processor:main',
        ],
    },
)
