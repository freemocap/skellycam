import React from 'react';
import {Box, Paper, Tooltip, Typography} from '@mui/material';
import FolderIcon from '@mui/icons-material/Folder';
import FolderSpecialIcon from '@mui/icons-material/FolderSpecial';import ChevronRightIcon from '@mui/icons-material/ChevronRight';

interface FullPathPreviewProps {
    directory: string;
    subfolder?: string;
    filename: string;
}

export const FullRecordingPathPreview: React.FC<FullPathPreviewProps> = ({
                                                                             directory,
                                                                             filename,
                                                                             subfolder
                                                                         }) => {
    const parts = [
        {icon: <FolderIcon/>, text: directory},
        ...(subfolder ? [{icon: <FolderIcon/>, text: subfolder}] : []),
        {icon: <FolderSpecialIcon/>, text: filename}
    ];

    const fullPath = parts.map(p => p.text).join('/');
    return (
        <Paper
            elevation={0}
            sx={{
                p: 1.5,
                backgroundColor: 'rgba(0, 0, 0, 0.04)',
                borderRadius: 1,
                borderStyle: 'solid',
                borderColor: 'rgba(0, 0, 0, 0.12)',
            }}
        >
            <Typography variant="body1" gutterBottom sx={{color: "#fff", mb: 1}}>
                Full Recording Path:
            </Typography>

            {/* Mobile/Narrow view */}
            <Box sx={{display: {xs: 'block', md: 'none'}}}>
                <Tooltip title={fullPath} placement="bottom-start">
                    <Typography
                        noWrap
                        sx={{
                            fontFamily: 'monospace',
                            fontSize: '0.9rem',
                            cursor: 'pointer'
                        }}
                    >
                        {fullPath}
                    </Typography>
                </Tooltip>
            </Box>

            {/* Desktop view */}
            <Box
                sx={{
                    display: {xs: 'none', md: 'flex'},
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: 0.5
                }}
            >
                {parts.map((part, index) => (
                    <React.Fragment key={index}>
                        <Box sx={{
                            display: 'flex',
                            alignItems: 'center',
                            color: 'text.secondary',
                            // backgroundColor: 'background.paper',
                            borderRadius: 1,
                            px: 1,
                            py: 0.5,
                        }}>
                            {part.icon}
                            <Typography
                                sx={{
                                    ml: 0.5,
                                    fontFamily: 'monospace',
                                    fontSize: '0.9rem'
                                }}
                            >
                                {part.text}
                            </Typography>
                        </Box>
                        {index < parts.length - 1 && (
                            <ChevronRightIcon sx={{color: 'text.secondary'}}/>
                        )}
                    </React.Fragment>
                ))}
            </Box>
        </Paper>
    );
};
