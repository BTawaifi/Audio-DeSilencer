from setuptools import setup, find_packages

with open('README.md', 'r', encoding='utf-8') as readme_file:
    long_description = readme_file.read()

setup(
    name='Audio-DeSilencer',
    version='1.0.2',
    description='An audio processing tool for detecting and removing silence in audio recordings.',
    author='Boutros Tawaifi',
    author_email='boutrous.m.tawaifi@gmail.com',
    license='MIT',
    url='https://github.com/BTawaifi/Audio-DeSilencer',
    packages=find_packages(),
    install_requires=[
        'pydub',
        'argparse',
    ],
    entry_points={
        'console_scripts': [
            'audio-desilencer=audio_desilencer.audio_processor:main',
        ],
    },
    keywords=['audio', 'processing', 'silence removal', 'pause removal'],
    long_description=long_description,
    long_description_content_type='text/markdown',
)
