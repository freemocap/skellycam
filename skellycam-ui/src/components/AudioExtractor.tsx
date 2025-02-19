//https://blog.kumard3.com/blog/extracting-audio-from-video-browser-react-ffmpeg-wasm
import React, {useRef, useState} from 'react'
import {FFmpeg} from '@ffmpeg/ffmpeg'
import {fetchFile, toBlobURL} from '@ffmpeg/util'

const AudioExtractor: React.FC = () => {
    const [loaded, setLoaded] = useState(false)
    const [videoFile, setVideoFile] = useState<File | null>(null)
    const [message, setMessage] = useState('')
    const ffmpegRef = useRef(new FFmpeg())

    const load = async () => {
        const baseURL = 'https://unpkg.com/@ffmpeg/core-mt@0.12.6/dist/esm'
        const ffmpeg = ffmpegRef.current
        ffmpeg.on('log', ({message}) => {
            setMessage(message)
        })
        await ffmpeg.load({
            coreURL: await toBlobURL(`${baseURL}/ffmpeg-core.js`, 'text/javascript'),
            wasmURL: await toBlobURL(`${baseURL}/ffmpeg-core.wasm`, 'application/wasm'),
            workerURL: await toBlobURL(`${baseURL}/ffmpeg-core.worker.js`, 'text/javascript'),
        })
        setLoaded(true)
    }

    const extractAudio = async () => {
        if (!videoFile) {
            alert('Please select an MP4 file first')
            return
        }
        const ffmpeg = ffmpegRef.current
        await ffmpeg.writeFile('input.mp4', await fetchFile(videoFile))
        await ffmpeg.exec([
            '-i',
            'input.mp4',
            '-vn',
            '-acodec',
            'libmp3lame',
            '-q:a',
            '2',
            'output.mp3',
        ])
        const data = await ffmpeg.readFile('output.mp3')
        const audioBlob = new Blob([data], {type: 'audio/mp3'})
        const audioUrl = URL.createObjectURL(audioBlob)
        const link = document.createElement('a')
        link.href = audioUrl
        link.download = 'extracted_audio.mp3'
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
    }

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        if (event.target.files && event.target.files[0]) {
            const file = event.target.files[0]
            if (file.type === 'video/mp4') {
                setVideoFile(file)
            } else {
                alert('Please select an MP4 file.')
                event.target.value = ''
            }
        }
    }

    return (
        <div className="my-8 rounded-lg border bg-gray-50 p-6">
            <h2 className="mb-4 text-2xl font-semibold">Audio Extractor</h2>
            {!loaded ? (
                <button
                    onClick={load}
                    className="rounded bg-blue-500 px-4 py-2 font-bold text-white hover:bg-blue-700"
                >
                    Load FFmpeg
                </button>
            ) : (
                <>
                    <input type="file" accept="video/mp4" onChange={handleFileChange} className="mb-4"/>
                    <br/>
                    <button
                        onClick={extractAudio}
                        disabled={!videoFile}
                        className="rounded bg-green-500 px-4 py-2 font-bold text-white hover:bg-green-700 disabled:opacity-50"
                    >
                        Extract Audio
                    </button>
                    <p className="mt-4 text-sm text-gray-600">{message}</p>
                </>
            )}
        </div>
    )
}

export default AudioExtractor
