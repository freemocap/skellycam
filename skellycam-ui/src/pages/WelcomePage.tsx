import React, {useEffect, useState, useRef, useCallback} from 'react';
import {Box, Checkbox, Container, Fade, FormControlLabel, Grow, Paper, Typography} from '@mui/material';
import {useNavigate} from 'react-router-dom';
import {useTheme} from '@mui/material/styles';
import {Footer} from '@/components/ui-components/Footer';
import {useElectronIPC} from "@/services";
import {useServer} from "@/services/server/ServerContextProvider";

const WelcomePage: React.FC = () => {
    const theme = useTheme();
    const navigate = useNavigate();
    const [logoDataUrl, setLogoDataUrl] = useState<string | null>(null);
    const [telemetryEnabled, setTelemetryEnabled] = useState<boolean>(true);
    const [telemetryLoaded, setTelemetryLoaded] = useState<boolean>(false);
    const {isElectron, api} = useElectronIPC();
    const {connectedCameraIds} = useServer();

    // Track previous camera count to detect 0 -> >0 transition
    const prevCountRef = useRef(connectedCameraIds.length);

    useEffect(() => {
        const prevCount = prevCountRef.current;
        const currentCount = connectedCameraIds.length;

        // Auto-navigate to cameras page only when first camera connects (0 -> >0 transition)
        if (prevCount === 0 && currentCount > 0) {
            navigate('/cameras');
        }

        prevCountRef.current = currentCount;
    }, [connectedCameraIds, navigate]);

    useEffect(() => {
        const fetchLogo = async (): Promise<void> => {
            try {
                if (isElectron && api) {
                    const dataUrl = await api.assets.getLogoBase64.query();
                    if (dataUrl) {
                        setLogoDataUrl(dataUrl);
                    } else {
                        console.warn('Logo image not found...');
                    }
                }
            } catch (error) {
                console.error('Failed to load logo:', error);
            }
        };

        fetchLogo();
    }, [isElectron, api]);

    // Load telemetry preference on mount
    useEffect(() => {
        const loadTelemetryPref = async (): Promise<void> => {
            try {
                if (isElectron && api) {
                    const enabled = await api.telemetry.getEnabled.query();
                    setTelemetryEnabled(enabled);
                }
            } catch (error) {
                console.error('Failed to load telemetry preference:', error);
            } finally {
                setTelemetryLoaded(true);
            }
        };

        loadTelemetryPref();
    }, [isElectron, api]);

    const handleTelemetryToggle = useCallback(async (_event: React.ChangeEvent<HTMLInputElement>, checked: boolean) => {
        setTelemetryEnabled(checked);
        try {
            if (isElectron && api) {
                await api.telemetry.setEnabled.mutate({enabled: checked});
            }
        } catch (error) {
            console.error('Failed to save telemetry preference:', error);
        }
    }, [isElectron, api]);

    return (
        <Container maxWidth="md" sx={{
            height: '100%',
            width: '100%',
            bgcolor: theme.palette.background.default,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            py: 4
        }}>
            <Fade in={true} timeout={800}>
                <Paper
                    elevation={6}
                    sx={{
                        p: {xs: 3, sm: 5},
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        width: '100%',
                        backgroundColor: theme.palette.background.paper,
                        mx: 'auto',
                        borderRadius: 3,
                        boxShadow: theme.palette.mode === 'dark'
                            ? '0 8px 32px rgba(0, 0, 0, 0.5)'
                            : '0 8px 32px rgba(0, 0, 0, 0.1)',
                        overflow: 'hidden',
                        position: 'relative'
                    }}
                >
                    {/* Background accent */}
                    <Box sx={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        height: '8px',
                        background: `linear-gradient(90deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                    }}/>

                    <Grow in={true} timeout={1000}>
                        <Box
                            sx={{
                                width: 240,
                                height: 240,
                                mb: 4,
                                mt: 2,
                                display: 'flex',
                                justifyContent: 'center',
                                alignItems: 'center',
                                transition: 'transform 0.3s ease-in-out',
                                '&:hover': {
                                    transform: 'scale(1.05)'
                                }
                            }}
                        >
                            {logoDataUrl && (
                                <img
                                    src={logoDataUrl}
                                    alt="SkellyCam Logo"
                                    style={{
                                        maxWidth: '100%',
                                        maxHeight: '100%',
                                        objectFit: 'contain',
                                        filter: theme.palette.mode === 'dark'
                                            ? 'drop-shadow(0 0 10px rgba(255,255,255,0.2))'
                                            : 'drop-shadow(0 0 10px rgba(0,0,0,0.1))'
                                    }}
                                />
                            )}
                        </Box>
                    </Grow>

                    <Typography
                        variant="h3"
                        component="h1"
                        gutterBottom
                        sx={{
                            fontWeight: 'bold',
                            textAlign: 'center',
                            background: theme.palette.text.primary,
                            WebkitBackgroundClip: 'text',
                            WebkitTextFillColor: 'transparent',
                            backgroundClip: 'text',
                            textFillColor: 'transparent',
                            mb: 2
                        }}
                    >
                        Welcome to SkellyCam
                    </Typography>

                    <Typography
                        variant="subtitle1"
                        color="text.secondary"
                        sx={{
                            mb: 3,
                            textAlign: 'center',
                            maxWidth: '80%',
                            fontSize: '1.1rem'
                        }}
                    >
                        Record and View Synchronized Videos
                    </Typography>

                    {/* Telemetry opt-in checkbox */}
                    {telemetryLoaded && (
                        <Fade in={true} timeout={600}>
                            <Box sx={{
                                mb: 3,
                                px: 2,
                                py: 1,
                                borderRadius: 2,
                                backgroundColor: theme.palette.mode === 'dark'
                                    ? 'rgba(255,255,255,0.03)'
                                    : 'rgba(0,0,0,0.02)',
                            }}>
                                <FormControlLabel
                                    control={
                                        <Checkbox
                                            checked={telemetryEnabled}
                                            onChange={handleTelemetryToggle}
                                            size="small"
                                        />
                                    }
                                    label={
                                        <Typography variant="body2" color="text.primary">
                                            Send anonymous usage pings
                                        </Typography>
                                    }
                                />
                            </Box>
                        </Fade>
                    )}

                    <Box component="footer" sx={{p: 3}}>
                        <Footer/>
                    </Box>
                </Paper>
            </Fade>
        </Container>
    );
};

export default WelcomePage;
