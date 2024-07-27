document.getElementById('captureButton').addEventListener('click', function() {
    document.getElementById('receipt').click();
});

document.getElementById('receipt').addEventListener('change', function(event) {
    const file = event.target.files[0];
    const reader = new FileReader();
    const preview = document.getElementById('preview');

    reader.onload = function(e) {
        const image = new Image();
        image.src = e.target.result;

        image.onload = function() {
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            canvas.width = image.width;
            canvas.height = image.height;
            context.drawImage(image, 0, 0);

            const imageData = canvas.toDataURL('image/png');
            document.getElementById('imageData').value = imageData;

            fetch('http://localhost:5000/ocr', {
                method: 'POST',
                body: JSON.stringify({ image: imageData }),
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                preview.innerHTML = `
                    <b>OR Number:</b> ${data.or_number}<br>
                    <b>Date:</b> ${data.date}<br>
                    <b>Time:</b> ${data.time}<br>
                    <b>Amount Paid:</b> ${data.amount_paid}<br>
                `;
            })
            .catch(error => {
                console.error('Error:', error);
                preview.textContent = 'Error processing the image.';
            });
        };
    };

    reader.readAsDataURL(file);
});

document.getElementById('submitButton').addEventListener('click', async function(event) {
    event.preventDefault();

    const formData = new FormData(document.getElementById('reimbursementForm'));
    formData.append('image', dataURItoBlob(document.getElementById('imageData').value));

    const response = await fetch('http://localhost:5000/submit', {
        method: 'POST',
        body: formData
    });

    const result = await response.json();
    alert(`Status: ${result.status}, Updated Range: ${result.updatedRange}`);
});

function dataURItoBlob(dataURI) {
    const byteString = atob(dataURI.split(',')[1]);
    const mimeString = dataURI.split(',')[0].split(':')[1].split(';')[0];
    const ab = new ArrayBuffer(byteString.length);
    const ia = new Uint8Array(ab);
    for (let i = 0; i < byteString.length; i++) {
        ia[i] = byteString.charCodeAt(i);
    }
    return new Blob([ab], { type: mimeString });
}
