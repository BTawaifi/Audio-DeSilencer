from setuptools import setup, find_packages

setup(
    name='Audio_DeSilencer',
    version='1.2',
    description='An audio processing tool for detecting and removing silence in audio recordings.',
    author='Boutros Tawaifi',
    author_email='boutrous.m.tawaifi@gmail.com',
    url='https://github.com/BTawaifi/Audio_DeSilencer',
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
