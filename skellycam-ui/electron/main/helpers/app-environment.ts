
// Set the process.env values
// process.env.NODE_ENV = 'development';
process.env.SHOULD_LAUNCH_PYTHON = 'false';


// Export the ENV_CONFIG object using the process.env values
export const APP_ENVIRONMENT = {
    IS_DEV: process.env.NODE_ENV === 'development',
    SHOULD_LAUNCH_PYTHON: process.env.SHOULD_LAUNCH_PYTHON === 'true',

};

// const checkAppPaths = () => {
//     Object.entries(APP_PATHS).forEach(([key, path]) => {
//         if (fs.existsSync(path)) {
//             console.log(`✓ ${key} exists at ${path}`);
//         } else {
//             console.log(`✗ ${key} does not exist at ${path}`);
//         }
//     });
// };
// checkAppPaths()
