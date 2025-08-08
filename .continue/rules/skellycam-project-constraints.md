---
description: SkellyCam Project constraints
---

This is the repository for SkellyCam, which is building a standalone desktop application that uses a Python FastAPI Backend server to connect to cameras using OpenCV and stream realtime images to a React/Electron/Typescript frontend. 

Speed and efficiency are critical in all cases, because this application must send around large images at high framerates in real time. 

We will do all communication within the same machine, so we don't need to worry about internet security stuff. We must be sure that our method work cross platform (Windows, Mac, Linux)