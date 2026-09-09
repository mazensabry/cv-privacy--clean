from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, Response
import fitz  # PyMuPDF
import re
import io
import zipfile

# إنشاء تطبيق FastAPI الرئيسي
app = FastAPI(title="oldorado CV Cleaner")

def redact_pdf_bytes(pdf_bytes: bytes) -> bytes:
    """
    دالة تقوم بقراءة ملف الـ PDF وطمس أرقام الهواتف والإيميلات والروابط والعناوين.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # أنماط التعبير النمطي (Regex) للبحث عن البيانات الحساسة
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_pattern = r'(?:\+\d{1,3}[\s-]?)?\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{4,}'
    url_pattern = r'(https?://\S+|www\.\S+|linkedin\.com/\S+|github\.com/\S+)'
    keywords = ["Address", "Location", "Street", "City", "العنوان", "المحافظة", "المدينة", "الشارع", "محل الإقامة"]

    for page in doc:
        text = page.get_text("text")
        rects = []

        # البحث عن الإيميلات والروابط والهواتف
        for email in re.findall(email_pattern, text):
            rects.extend(page.search_for(email))
        for url in re.findall(url_pattern, text):
            rects.extend(page.search_for(url))
        for phone in re.findall(phone_pattern, text):
            match_str = phone[0] if isinstance(phone, tuple) else phone
            clean_phone = match_str.strip()
            if len(re.sub(r'\D', '', clean_phone)) >= 7:
                rects.extend(page.search_for(clean_phone))
        for kw in keywords:
            for rect in page.search_for(kw):
                extended = fitz.Rect(rect.x0 - 50, rect.y0 - 5, rect.x1 + 300, rect.y1 + 5)
                rects.append(extended)

        # تطبيق المستطيلات السوداء للطمس
        for rect in rects:
            page.add_redact_annot(rect, fill=(0, 0, 0))
        page.apply_redactions()

    output_stream = io.BytesIO()
    doc.save(output_stream)
    doc.close()
    return output_stream.getvalue()

@app.get("/", response_class=HTMLResponse)
async def main_page():
    """
    عرض واجهة المستخدم السريعة عبر HTML
    """
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>oldorado | CV Privacy Shield</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 20px; display: flex; justify-content: center; }
            .container { max-width: 500px; width: 100%; background: #1e293b; padding: 25px; border-radius: 14px; border: 1px solid #334155; box-shadow: 0 10px 25px rgba(0,0,0,0.3); text-align: center; }
            h1 { color: #38bdf8; font-size: 22px; margin-bottom: 5px; }
            p { color: #94a3b8; font-size: 14px; margin-top: 0; }
            .upload-box { border: 2px dashed #38bdf8; border-radius: 10px; padding: 20px; margin: 20px 0; background: #0f172a; cursor: pointer; }
            input[type="file"] { display: none; }
            .btn-select { background: #0284c7; color: white; padding: 10px 18px; border-radius: 8px; font-weight: bold; cursor: pointer; display: inline-block; }
            .btn-submit { background: #10b981; color: white; border: none; padding: 14px; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; font-size: 16px; margin-top: 15px; }
            .btn-submit:disabled { background: #475569; cursor: not-allowed; }
            #file-list { margin-top: 10px; font-size: 13px; color: #38bdf8; text-align: right; max-height: 100px; overflow-y: auto; }
            #status { margin-top: 15px; font-weight: bold; font-size: 14px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>oldorado | CV Privacy Shield</h1>
            <p>إزالة بيانات التواصل من الـ CVs قبل إرسالها لأصحاب العمل</p>
            
            <form id="uploadForm">
                <div class="upload-box" onclick="document.getElementById('fileInput').click()">
                    <span class="btn-select">📂 اختر ملفات الـ CVs</span>
                    <input type="file" id="fileInput" name="files" multiple accept="application/pdf" onchange="updateFilesList()">
                    <div id="file-list">لم يتم اختيار ملفات بعد</div>
                </div>
                <button type="submit" id="submitBtn" class="btn-submit" disabled>🚀 معالجة وتنظيف الـ CVs</button>
            </form>
            <div id="status"></div>
        </div>

        <script>
            const fileInput = document.getElementById('fileInput');
            const fileList = document.getElementById('file-list');
            const submitBtn = document.getElementById('submitBtn');
            const statusDiv = document.getElementById('status');

            function updateFilesList() {
                const files = fileInput.files;
                if (files.length === 0) {
                    fileList.innerHTML = 'لم يتم اختيار ملفات بعد';
                    submitBtn.disabled = true;
                    return;
                }
                fileList.innerHTML = `تم اختيار <b>${files.length}</b> ملفات.`;
                submitBtn.disabled = false;
            }

            document.getElementById('uploadForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const files = fileInput.files;
                if (files.length === 0) return;

                statusDiv.style.color = '#38bdf8';
                statusDiv.innerText = '⏳ جاري المعالجة وإخفاء البيانات...';
                submitBtn.disabled = true;

                const formData = new FormData();
                for (let i = 0; i < files.length; i++) {
                    formData.append('files', files[i]);
                }

                try {
                    const response = await fetch('/clean', {
                        method: 'POST',
                        body: formData
                    });

                    if (!response.ok) throw new Error('فشلت المعالجة');

                    const blob = await response.blob();
                    const downloadUrl = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = downloadUrl;

                    if (files.length === 1) {
                        a.download = 'Cleaned_' + files[0].name;
                    } else {
                        a.download = 'oldorado_Cleaned_CVs.zip';
                    }

                    document.body.appendChild(a);
                    a.click();
                    a.remove();

                    statusDiv.style.color = '#10b981';
                    statusDiv.innerText = '🎉 تم التحميل بنجاح!';
                } catch (err) {
                    statusDiv.style.color = '#ef4444';
                    statusDiv.innerText = '❌ حدث خطأ أثناء المعالجة، حاول مجدداً.';
                } finally {
                    submitBtn.disabled = false;
                }
            });
        </script>
    </body>
    </html>
    """

@app.post("/clean")
async def clean_cvs(files: list[UploadFile] = File(...)):
    if len(files) == 1:
        file = files[0]
        content = await file.read()
        cleaned = redact_pdf_bytes(content)
        return Response(
            content=cleaned,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=Cleaned_{file.filename}"}
        )
    else:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file in files:
                content = await file.read()
                cleaned = redact_pdf_bytes(content)
                zip_file.writestr(f"Cleaned_{file.filename}", cleaned)

        zip_buffer.seek(0)
        return Response(
            content=zip_buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=oldorado_Cleaned_CVs.zip"}
        )
