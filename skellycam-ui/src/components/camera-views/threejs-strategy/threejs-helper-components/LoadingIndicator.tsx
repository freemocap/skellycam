// Loading indicator
import {Html} from "@react-three/drei";
import React from "react";

export function LoadingIndicator() {
    return (
        <Html center>
            <div style={{color: 'white', background: 'rgba(0,0,0,0.7)', padding: '12px 24px', borderRadius: '4px'}}>
                Loading...
            </div>
        </Html>
    );
}
