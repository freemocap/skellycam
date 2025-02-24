import * as React from 'react';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import Box from "@mui/material/Box";
import extendedPaperbaseTheme from "@/layout/paperbase_theme/paperbase-theme";
import {List, ListItem, Paper} from "@mui/material";
import WebsocketConnectionStatus from "@/components/WebsocketConnectionStatus";
import {ConfigView} from "@/components/config-views/ConfigView";


const item = {
    py: '2px',
    px: 3,
    color: extendedPaperbaseTheme.palette.primary.contrastText,
    '&:hover, &:focus': {
        bgcolor: 'rgba(255, 255, 255, 0.08)',
    },
};

const itemCategory = {
    boxShadow: '0 -1px 0 rgb(255,255,255,0.1) inset',
    py: 1.5,
    px: 3,
};

export const LeftSidePanelContent = () => {
    return (
        <Box sx={{
            width: '100%',
            height: '100%',
            backgroundColor: extendedPaperbaseTheme.palette.primary.dark,
            color: extendedPaperbaseTheme.palette.primary.contrastText
        }}>

            <List disablePadding>
                <ListItem sx={{...item, ...itemCategory, fontSize: 22, color: '#fafafa'}}>
                    SkellyCam💀📸
                </ListItem>
            </List>
            <WebsocketConnectionStatus/>

                <Accordion>
                    <AccordionSummary
                        expandIcon={<ExpandMoreIcon sx={{color: extendedPaperbaseTheme.palette.primary.contrastText}}/>}
                        sx={{
                            backgroundColor: extendedPaperbaseTheme.palette.primary.main,
                            color: extendedPaperbaseTheme.palette.primary.contrastText,
                            boxShadow: `0 -1px 0 ${extendedPaperbaseTheme.palette.primary.light}`,
                        }}
                    >
                        <Typography>Available Cameras</Typography>
                    </AccordionSummary>
                    <AccordionDetails
                        sx={{
                            backgroundColor: extendedPaperbaseTheme.palette.primary.main,
                            color: extendedPaperbaseTheme.palette.primary.contrastText
                        }}
                    >
                        <ConfigView/>
                    </AccordionDetails>
                </Accordion>
                <Paper/>
        </Box>
);
}
