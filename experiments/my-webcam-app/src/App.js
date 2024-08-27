import React, {useEffect, useRef, useState} from 'react';
import Webcam from 'react-webcam';
import {saveAs} from 'file-saver';

const ffmpeg = createFFmpeg({log: true});

const WebcamComponent = ({
                             device,
                             isGlobalRecording,
                             onRecordingComplete,
                         }) => {
    const webcamRef = useRef(null);
    const mediaRecorderRef = useRef(null);
    const [localRecording, setLocalRecording] = useState(false);
    const [recordedChunks, setRecordedChunks] = useState([]);

    useEffect(() => {
        if (isGlobalRecording && !localRecording) {
            handleStartCaptureClick();
        } else if (!isGlobalRecording && localRecording) {
            handleStopCaptureClick();
        }
    }, [isGlobalRecording, localRecording]);

    const handleStartCaptureClick = () => {
        setLocalRecording(true);
        mediaRecorderRef.current = new MediaRecorder(webcamRef.current.stream, {
            mimeType: 'video/webm',
        });
        mediaRecorderRef.current.addEventListener(
            'dataavailable',
            handleDataAvailable,
        );
        mediaRecorderRef.current.start();
    };

    const handleDataAvailable = ({data}) => {
        if (data.size > 0) {
            setRecordedChunks((prev) => prev.concat(data));
        }
    };

    const handleStopCaptureClick = () => {
        mediaRecorderRef.current.stop();
        setLocalRecording(false);
    };

    const handleSave = () => {
        if (recordedChunks.length) {
            const blob = new Blob(recordedChunks, {
                type: 'video/webm',
            });
            saveAs(blob, `recording_${device.label}.webm`);
            setRecordedChunks([]);
            onRecordingComplete(device.deviceId);
        }
    };

    useEffect(() => {
        if (!isGlobalRecording && recordedChunks.length > 0) {
            handleSave();
        }
    }, [isGlobalRecording, recordedChunks]);

    return (
        <div style={{margin: '5px'}}>
            <Webcam
                audio={false}
                ref={webcamRef}
                videoConstraints={{deviceId: device.deviceId}}
            />
        </div>
    );
};

const WebcamGrid = () => {
    const [devices, setDevices] = useState([]);
    const [isGlobalRecording, setIsGlobalRecording] = useState(false);

    useEffect(() => {
        const getDevices = async () => {
            try {
                const devices = await navigator.mediaDevices.enumerateDevices();
                const videoDevices = devices.filter(
                    (device) => device.kind === 'videoinput',
                );
                setDevices(videoDevices);
            } catch (error) {
                console.error('Error accessing media devices:', error);
            }
        };

        getDevices();
    }, []);

    const handleGlobalRecording = () => {
        setIsGlobalRecording(!isGlobalRecording);
    };

    const onRecordingComplete = (deviceId) => {
        // Additional logic can be added here if needed when a recording completes
    };

    return (
        <div>
            <button onClick={handleGlobalRecording}>
                {isGlobalRecording ? 'Stop Recording All' : 'Record from Everything'}
            </button>
            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
                    gap: '10px',
                }}
            >
                {devices.map((device, index) => (
                    <WebcamComponent
                        key={device.deviceId}
                        device={device}
                        isGlobalRecording={isGlobalRecording}
                        onRecordingComplete={onRecordingComplete}
                    />
                ))}
            </div>
        </div>
    );
};

function App() {
    return (
        <div className="App">
            <h1>Multiple Webcams with Global Recording</h1>
            <WebcamGrid/>
        </div>
    );
}

export default App;

// import React, { useState, useEffect, useRef } from 'react';
// import Webcam from 'react-webcam';
// import { saveAs } from 'file-saver';
//
// const WebcamComponent = ({ device }) => {
//   const webcamRef = useRef(null);
//   const mediaRecorderRef = useRef(null);
//   const [capturing, setCapturing] = useState(false);
//   const [recordedChunks, setRecordedChunks] = useState([]);
//
//   const handleStartCaptureClick = () => {
//     setCapturing(true);
//     mediaRecorderRef.current = new MediaRecorder(webcamRef.current.stream, {
//       mimeType: 'video/webm',
//     });
//     mediaRecorderRef.current.addEventListener(
//       'dataavailable',
//       handleDataAvailable,
//     );
//     mediaRecorderRef.current.start();
//   };
//
//   const handleDataAvailable = ({ data }) => {
//     if (data.size > 0) {
//       setRecordedChunks((prev) => prev.concat(data));
//     }
//   };
//
//   const handleStopCaptureClick = () => {
//     mediaRecorderRef.current.stop();
//     setCapturing(false);
//   };
//
//   const handleSave = () => {
//     if (recordedChunks.length) {
//       const blob = new Blob(recordedChunks, {
//         type: 'video/webm',
//       });
//       saveAs(blob, `recording_${device.label}.webm`);
//       setRecordedChunks([]);
//     }
//   };
//
//   return (
//     <div style={{ margin: '5px' }}>
//       <Webcam
//         audio={false}
//         ref={webcamRef}
//         videoConstraints={{ deviceId: device.deviceId }}
//       />
//       {capturing ? (
//         <button onClick={handleStopCaptureClick}>Stop Capture</button>
//       ) : (
//         <button onClick={handleStartCaptureClick}>Start Capture</button>
//       )}
//       {recordedChunks.length > 0 && (
//         <button onClick={handleSave}>Save Recording</button>
//       )}
//     </div>
//   );
// };
//
// const WebcamGrid = () => {
//   const [devices, setDevices] = useState([]);
//
//   useEffect(() => {
//     const getDevices = async () => {
//       try {
//         const devices = await navigator.mediaDevices.enumerateDevices();
//         const videoDevices = devices.filter(
//           (device) => device.kind === 'videoinput',
//         );
//         setDevices(videoDevices);
//       } catch (error) {
//         console.error('Error accessing media devices:', error);
//       }
//     };
//
//     getDevices();
//   }, []);
//
//   return (
//     <div
//       style={{
//         display: 'grid',
//         gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
//         gap: '10px',
//       }}
//     >
//       {devices.map((device, index) => (
//         <WebcamComponent key={device.deviceId} device={device} />
//       ))}
//     </div>
//   );
// };
//
// function App() {
//   return (
//     <div className="App">
//       <h1>Multiple Webcams with Recording</h1>
//       <WebcamGrid />
//     </div>
//   );
// }
//
// export default App;
//
// // import React, { useState, useEffect } from 'react';
// // import Webcam from 'react-webcam';
// //
// // const WebcamGrid = () => {
// //   const [devices, setDevices] = useState([]);
// //
// //   useEffect(() => {
// //     const getDevices = async () => {
// //       try {
// //         const devices = await navigator.mediaDevices.enumerateDevices();
// //         const videoDevices = devices.filter(
// //           (device) => device.kind === 'videoinput',
// //         );
// //         setDevices(videoDevices);
// //       } catch (error) {
// //         console.error('Error accessing media devices:', error);
// //       }
// //     };
// //
// //     getDevices();
// //   }, []);
// //
// //   return (
// //     <div
// //       style={{
// //         display: 'grid',
// //         gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
// //         gap: '10px',
// //       }}
// //     >
// //       {devices.map((device, index) => (
// //         <Webcam
// //           key={device.deviceId}
// //           audio={false}
// //           videoConstraints={{ deviceId: device.deviceId }}
// //           style={{ width: '100%' }}
// //         />
// //       ))}
// //     </div>
// //   );
// // };
// //
// // function App() {
// //   return (
// //     <div className="App">
// //       <h1>Multiple Webcams</h1>
// //       <WebcamGrid />
// //     </div>
// //   );
// // }
// //
// // export default App;
