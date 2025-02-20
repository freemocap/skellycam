import * as React from 'react';
import Drawer, {DrawerProps} from '@mui/material/Drawer';
import {useNavigate} from "react-router";
import {extendedPaperbaseTheme} from "@/layout/base-content/paperbase_theme/paperbase-theme";
import {Divider, List, ListItem, ListItemButton, ListItemText} from "@mui/material";
import Box from "@mui/material/Box";
import WebsocketConnectionStatus from "@/components/WebsocketConnectionStatus";
import {ConnectToCamerasButton} from "@/components/ConnectToCamerasButton";

const sidebarItems = [
    {
        id: 'Views',
        children: [
            {
                id: 'Camera Views',
                route: "/"
            },
            {
                id: "Config View",
                route: "/config"
            }
        ],
    },
];

const item = {
    py: '2px',
    px: 3,
    color: 'rgb(250,250,250)',
    '&:hover, &:focus': {
        bgcolor: 'rgba(255, 255, 255, 0.08)',
    },
};

const itemCategory = {
    boxShadow: '0 -1px 0 rgb(255,255,255,0.1) inset',
    py: 1.5,
    px: 3,
};

export const LeftSidebarDrawer = function (props: DrawerProps) {
    const {...other} = props;
    const navigate = useNavigate();

    return (
        <Drawer
            variant="permanent"
            sx={{
                width: '100%', //full width of parent panel


            }}
            {...other}
        >
            <Drawer variant="permanent" {...other}>
                <List disablePadding>
                    <ListItem sx={{...item, ...itemCategory, fontSize: 22, color: '#fafafa'}}>
                        SkellyCam💀📸
                    </ListItem>
                    {sidebarItems.map(({id, children}) => (
                        <Box key={id} sx={{bgcolor: '#101F33'}}>
                            <ListItem sx={{py: 2, px: 3}}>
                                <ListItemText sx={{color: '#fafafa'}}>{id}</ListItemText>
                            </ListItem>
                            {children.map(({id: childId, route}) => (
                                <ListItem disablePadding key={childId}>
                                    <ListItemButton selected={false} sx={item} onClick={() => {
                                        navigate(route)
                                    }}>
                                        <ListItemText>{childId}</ListItemText>
                                    </ListItemButton>
                                </ListItem>
                            ))}
                            <Divider sx={{mt: 2}}/>
                        </Box>
                    ))}
                </List>
                <WebsocketConnectionStatus/>
                <ConnectToCamerasButton/>

            </Drawer>
        </Drawer>
    )
}
