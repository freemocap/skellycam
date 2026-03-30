import React, {useEffect, useState, useRef, useCallback} from 'react';
import {Box, Button, Checkbox, CircularProgress, Container, Fade, FormControlLabel, Grow, Paper, Stack, Typography} from '@mui/material';
import {useNavigate} from 'react-router-dom';
import {useTheme} from '@mui/material/styles';
import VideocamIcon from '@mui/icons-material/Videocam';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import {Footer} from '@/components/ui-components/Footer';
import {useElectronIPC} from "@/services";
import {useServer} from "@/services/server/ServerContextProvider";
import {useTranslation} from "react-i18next";
import {LanguageSwitcher} from "@/components/languages/LanguageSwitcher";
import {VersionChip} from "@/components/ui-components/VersionChip";
import {useAppDispatch} from "@/store";
import {camerasConnectOrUpdate} from "@/store/slices/cameras/cameras-thunks";
import {EXTERNAL_URLS} from "@/constants/external-urls";

const WelcomePage: React.FC = () => {
    const {t} = useTranslation();
    const theme = useTheme();
    const navigate = useNavigate();
    const [logoDataUrl, setLogoDataUrl] = useState<string | null>(null);
    const [telemetryEnabled, setTelemetryEnabled] = useState<boolean>(true);
    const [telemetryLoaded, setTelemetryLoaded] = useState<boolean>(false);
    const {isElectron, api} = useElectronIPC();
    const {connectedCameraIds} = useServer();
    const dispatch = useAppDispatch();
    const [isConnecting, setIsConnecting] = useState(false);

    // Track previous camera count to detect 0 -> >0 transition
    const prevCountRef = useRef(connectedCameraIds.length);

    useEffect(() => {
        const prevCount = prevCountRef.current;
        const currentCount = connectedCameraIds.length;

        // Auto-navigate to cameras page when first camera connects (0 -> >0 transition)
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

    const handleConnectCameras = useCallback(async () => {
        setIsConnecting(true);
        try {
            await dispatch(camerasConnectOrUpdate()).unwrap();
        } catch (error) {
            console.error('Error connecting cameras:', error);
        } finally {
            setIsConnecting(false);
        }
    }, [dispatch]);

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
                        {t('welcomeTitle')}
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
                        {t('welcomeSubtitle')}
                    </Typography>

                    {/* Connect to Cameras button */}
                    <Button
                        variant="contained"
                        size="large"
                        color="primary"
                        startIcon={isConnecting
                            ? <CircularProgress size={20} color="inherit" />
                            : <VideocamIcon />
                        }
                        onClick={handleConnectCameras}
                        disabled={isConnecting}
                        sx={{
                            mb: 3,
                            px: 4,
                            py: 1.5,
                            fontSize: '1.1rem',
                            borderRadius: 2,
                            textTransform: 'none',
                        }}
                    >
                        {t('connectToCameras')}
                    </Button>

                    {/* External links */}
                    <Stack direction="row" spacing={2} sx={{mb: 3}}>
                        <Button
                            variant="outlined"
                            size="small"
                            endIcon={<OpenInNewIcon sx={{fontSize: 14}} />}
                            onClick={() => window.open(EXTERNAL_URLS.DOCS, '_blank')}
                            sx={{textTransform: 'none'}}
                        >
                            {t('documentation')}
                        </Button>
                        <Button
                            variant="outlined"
                            size="small"
                            endIcon={<OpenInNewIcon sx={{fontSize: 14}} />}
                            onClick={() => window.open(EXTERNAL_URLS.ROADMAP, '_blank')}
                            sx={{textTransform: 'none'}}
                        >
                            {t('roadmap')}
                        </Button>
                    </Stack>

                    {/* Language selector */}
                    <Box sx={{mb: 3}}>
                        <LanguageSwitcher/>
                    </Box>

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
                                            {t('sendAnonymousPings')}
                                        </Typography>
                                    }
                                />
                            </Box>
                        </Fade>
                    )}

                    <Box component="footer" sx={{p: 3, textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1}}>
                        <Footer/>
                        <VersionChip variant="compact" />
                    </Box>
                </Paper>
            </Fade>
        </Container>
    );
};

export default WelcomePage;
