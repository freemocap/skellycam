use std::sync::mpsc::{self, Receiver};
use std::sync::Arc;
use std::thread::JoinHandle;

use crate::camera::{self, CameraHandle, MultiFramePayload};
use crate::sync_utils::BreakableBarrier;
use super::gatherer::spawn_gatherer;
use super::types::CameraGroupConfig;

pub struct CameraGroup {
    pub camera_handles: Vec<CameraHandle>,
    pub multi_frame_receiver: Receiver<MultiFramePayload>,
    gatherer_handle: Option<JoinHandle<()>>,
    barrier: Arc<BreakableBarrier>,
}

impl CameraGroup {
    pub fn create(configs: Vec<CameraGroupConfig>) -> anyhow::Result<Self> {
        if configs.is_empty() {
            anyhow::bail!("CameraGroup requires at least one camera config");
        }

        let camera_count = configs.len();
        eprintln!("[CameraGroup] starting {camera_count} camera(s) in lockstep");

        let barrier = Arc::new(BreakableBarrier::new(camera_count + 1));

        let mut camera_handles = Vec::with_capacity(camera_count);
        let mut frame_receivers = Vec::with_capacity(camera_count);
        let mut event_receivers = Vec::with_capacity(camera_count);

        for config in configs {
            let (handle, event_receiver, frame_receiver) = camera::spawn_camera_thread(
                &config.capture_config,
                config.identity,
                barrier.clone(),
            );
            camera_handles.push(handle);
            frame_receivers.push(frame_receiver);
            event_receivers.push(event_receiver);
        }

        let (multi_frame_sender, multi_frame_receiver) = mpsc::sync_channel(1);

        let gatherer_handle = spawn_gatherer(
            frame_receivers,
            event_receivers,
            camera_handles.clone(),
            multi_frame_sender,
            barrier.clone(),
        );

        Ok(CameraGroup {
            camera_handles,
            multi_frame_receiver,
            gatherer_handle: Some(gatherer_handle),
            barrier,
        })
    }

    pub fn shutdown(&self) {
        tracing::info!("CameraGroup: sending shutdown to all cameras");
        for handle in &self.camera_handles {
            handle.send_shutdown();
        }
        self.barrier.break_barrier();
    }

    pub fn wait_for_shutdown(mut self) {
        if let Some(handle) = self.gatherer_handle.take() {
            let _ = handle.join();
        }
    }
}

impl Drop for CameraGroup {
    fn drop(&mut self) {
        for handle in &self.camera_handles {
            handle.send_shutdown();
        }
    }
}
