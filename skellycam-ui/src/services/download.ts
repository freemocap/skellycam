export const download = (inputBlob: Blob, outputFileName: string) => {
  const url = URL.createObjectURL(inputBlob);
  const a = document.createElement("a");
  document.body.appendChild(a);
  a.style.display = "none";
  a.href = url;
  a.download = outputFileName;
  a.click();
  window.URL.revokeObjectURL(url);
}
