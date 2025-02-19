import { Box } from "@mui/material"
import React from "react"
import "./WelcomeView.css"

const logoUrl =
  "https://media.githubusercontent.com/media/freemocap/skellysubs/3b64fa9bb6843529df050c5373c2773f4bb0e2f4/skellysubs-ui/src/assets/skellysubs-logo.png"

export const WelcomeView = () => {
  return (
    <Box className="welcome-container">
      <img src={logoUrl} alt="SkellySubs Logo" className="welcome-logo" />
      <Box>Welcome to SkellySubs</Box>
    </Box>
  )
}
