/**
 * Reads an image file, draws it to a canvas, and exports it as a Blob,
 * effectively stripping metadata.
 * @param {File} file The image file to process.
 * @returns {Promise<Blob>} A promise that resolves with the new Blob without metadata.
 */
function stripImageMetadata(file) {
    return new Promise((resolve, reject) => {
        if (!file.type.startsWith('image/')) {
            // If it's not an image, resolve with the original file
            resolve(file);
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                // Maintain original dimensions
                canvas.width = img.naturalWidth;
                canvas.height = img.naturalHeight;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0);

                // Export from canvas
                // Use file.type to preserve original image format (jpeg vs png)
                // Quality parameter only applies to 'image/jpeg' or 'image/webp'
                canvas.toBlob((blob) => {
                    if (blob) {
                        // Resolve with the new Blob
                        resolve(blob);
                    } else {
                        console.error("Canvas to Blob conversion failed for", file.name, "- returning original file.");
                        resolve(file); // Fallback to original file on error
                    }
                }, file.type, 0.9); // Quality 0.9 for JPEG/WebP
            };
            img.onerror = () => {
                console.error("Could not load image:", file.name, "- returning original file.");
                resolve(file); // Fallback to original file on error
            };
            img.src = e.target.result; // Set source after onload/onerror are defined
        };
        reader.onerror = () => {
            console.error("Could not read file:", file.name, "- returning original file.");
            resolve(file); // Fallback to original file on error
        };
        reader.readAsDataURL(file);
    });
}

/**
 * Processes form data, stripping metadata from image files before submission.
 * @param {string} formId The ID of the form element.
 * @param {string} fileInputName The 'name' attribute of the file input element.
 * @returns {Promise<FormData>} A promise that resolves with the processed FormData object.
 */
async function processFormData(formId, fileInputName) {
    const form = document.getElementById(formId);
    if (!form) {
        throw new Error(`Form with ID "${formId}" not found.`);
    }
    const originalFormData = new FormData(form);
    const processedFormData = new FormData();
    const fileInput = form.querySelector(`input[name="${fileInputName}"]`);
    if (!fileInput) {
        console.warn(`File input with name "${fileInputName}" not found in form "${formId}". Proceeding without file processing.`);
         // If no file input, just return original data
        return originalFormData;
    }
    const files = fileInput.files;

    // 1. Append all non-file fields first
    for (const [key, value] of originalFormData.entries()) {
        // Check if the value is NOT a File object OR if it's not the file input we are processing
        // This ensures other potential file inputs (if any) are also copied initially.
        // We will overwrite the specific fileInputName entries later.
        if (!(value instanceof File) || key !== fileInputName) {
             processedFormData.append(key, value);
        }
    }

    // 2. Process and append files from the specified file input
    const processingPromises = [];
    if (files && files.length > 0) {
        for (const file of files) {
            // Process only image files, pass others directly
            const promise = stripImageMetadata(file).then(processedBlobOrFile => {
                 // Use the original filename, but with the potentially new Blob data
                processedFormData.append(fileInputName, processedBlobOrFile, file.name);
            });
            processingPromises.push(promise);
        }
        // Wait for all file processing promises to resolve
        await Promise.all(processingPromises);
        console.log("All images processed and metadat removed successfully.")
    } else {
         // If no files selected, ensure the file input field still exists in FormData if needed by backend
         // However, FormData usually omits fields with no files selected.
         // If the backend *requires* the field even if empty, you might need:
         // processedFormData.append(fileInputName, ''); // Or an empty blob: new Blob([])
         console.log("No files selected for processing.");
    }


    return processedFormData;
}
