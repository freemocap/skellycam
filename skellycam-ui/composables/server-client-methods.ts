export const fetchHello = async () => {
    const response = await fetch('http://localhost:8005/app/healthcheck');
    const data = await response.json();
    console.log(data);
}
export const fetchAppState = async () => {
    const response = await fetch('http://localhost:8005/app/state');
    const data = await response.json();
    console.log(data);
}
export const connectToCameras = async () => {
    const response = await fetch('http://localhost:8005/cameras/connect');
    const data = await response.json();
    console.log(data);
}
export const closeCameras = async () => {
    const response = await fetch('http://localhost:8005/cameras/close');
    const data = await response.json();
    console.log(data);
}
