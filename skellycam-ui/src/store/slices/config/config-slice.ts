import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface ServerConfig {
    host: string;
    port: number;
}

interface ConfigState {
    server: ServerConfig;
}

const initialState: ConfigState = {
    server: {
        host: localStorage.getItem('server-host') || 'localhost',
        port: parseInt(localStorage.getItem('server-port') || '8006'),
    },
};

export const configSlice = createSlice({
    name: 'config',
    initialState,
    reducers: {
        serverConfigUpdated: (state, action: PayloadAction<Partial<ServerConfig>>) => {
            state.server = { ...state.server, ...action.payload };
            // Persist to localStorage
            localStorage.setItem('server-host', state.server.host);
            localStorage.setItem('server-port', state.server.port.toString());
        },
    },
});

export const { serverConfigUpdated } = configSlice.actions;
