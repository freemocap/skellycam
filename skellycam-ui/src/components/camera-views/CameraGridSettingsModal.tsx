import React, { useEffect, useRef, useState } from 'react';
import { CameraConfigPanel } from '@/components/camera-config-panel/CameraConfigPanel';
import { useAppDispatch } from '@/store';
import { cameraDesiredConfigUpdated } from '@/store/slices/cameras/cameras-slice';
import { Camera, CameraConfig } from '@/store/slices/cameras/cameras-types';

interface CameraGridSettingsModalProps {
    camera: Camera;
    initialPos: { top: number; right: number };
    onClose: () => void;
}

export const CameraGridSettingsModal: React.FC<CameraGridSettingsModalProps> = ({ camera, initialPos, onClose }) => {
    const dispatch = useAppDispatch();
    const [pos, setPos] = useState(initialPos);
    const dragRef = useRef<{ startX: number; startY: number; startTop: number; startRight: number } | null>(null);

    useEffect(() => {
        const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [onClose]);

    const handleConfigChange = (newConfig: CameraConfig) => {
        dispatch(cameraDesiredConfigUpdated({ cameraId: camera.id, config: newConfig }));
    };

    const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
        if ((e.target as HTMLElement).closest('button, input, select')) return;
        e.currentTarget.setPointerCapture(e.pointerId);
        dragRef.current = { startX: e.clientX, startY: e.clientY, startTop: pos.top, startRight: pos.right };
        e.currentTarget.style.cursor = 'grabbing';
    };

    const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
        if (!dragRef.current || !e.currentTarget.hasPointerCapture(e.pointerId)) return;
        const dx = e.clientX - dragRef.current.startX;
        const dy = e.clientY - dragRef.current.startY;
        setPos({ top: dragRef.current.startTop + dy, right: dragRef.current.startRight - dx });
    };

    const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
        if (dragRef.current) {
            e.currentTarget.releasePointerCapture(e.pointerId);
            e.currentTarget.style.cursor = 'grab';
            dragRef.current = null;
        }
    };

    return (
        <div
            className="camera-grid-settings-modal bg-dark border-1 border-black br-2 elevated-sharp flex flex-col p-1 gap-1 reveal fadeIn"
            style={{ position: 'fixed', top: pos.top, right: pos.right, zIndex: 300, width: 240, overflow: 'hidden', cursor: 'grab' }}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onClick={(e) => e.stopPropagation()}
        >
            <div className="flex items-center justify-content-space-between bg-middark br-1 p-1">
                <p className="text sm text-gray">Camera #{camera.index} · {camera.id}</p>
                <button className="button icon-button" onClick={onClose}>
                    <span className="icon close-icon icon-size-16" />
                </button>
            </div>

            <div className="bg-middark br-1 p-1">
                <CameraConfigPanel
                    config={camera.desiredConfig}
                    onConfigChange={handleConfigChange}
                    isExpanded={true}
                    compact
                />
            </div>
        </div>
    );
};
