import {execa} from 'execa';
import * as path from 'path';
import {dirname} from 'path';
import {promises as fs} from 'fs';
import {fileURLToPath} from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

async function main() {
    const scriptName = process.platform === 'win32' ? 'install-python.bat' : 'install-python.sh';
    const scriptPath = path.join(__dirname, scriptName);
    console.log(`\n----------------------\n CREATING ||PYTHON|| BINARY FOR ||TAURI|| SIDECAR\n---------------------\n`);
    console.log(`Preparing to run ${scriptName}...`);

    if (process.platform !== 'win32') {
        console.log('Setting script permissions to be executable...');
        await fs.chmod(scriptPath, 0o755);
    }

    try {
        console.log('Running the install script...');

        await execa(scriptPath, {stdio: 'inherit'});
        console.log(`${scriptName} executed successfully!!`);
    } catch (error) {
        console.error(`Failed to execute ${scriptName}:`, error);
    }
}

main().catch((error) => {
    console.error('An error occurred:', error);
});