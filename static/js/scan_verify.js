// ============================================================
// SCAN & VERIFY: upload PDF -> tokenisasi (pdfplumber) -> CRF
// -> isi tabel hasil ekstraksi (tidak ada data dummy).
// ============================================================
document.addEventListener("DOMContentLoaded", function () {
  const dropZone = document.getElementById("drop_zone");
  const uploadLink = document.getElementById("upload_link");
  const fileInput = document.getElementById("fileInput");
  const fileChip = document.getElementById("fileChip");
  const fileChipName = document.getElementById("fileChipName");
  const fileChipRemove = document.getElementById("fileChipRemove");
  const uploadAlert = document.getElementById("uploadAlert");
  const statusBadge = document.getElementById("statusBadge");
  const uploadIcon = document.getElementById("uploadIcon");
  const uploadSpinner = document.getElementById("uploadSpinner");
  const tableBody = document.getElementById("bpdTableBody");
  const emptyRow = document.getElementById("emptyRow");
  const viewOriginalBtn = document.getElementById("viewOriginalBtn");

  // Only run this block on the Scan & Verify page.
  if (!dropZone || !fileInput || !tableBody) return;

  const fieldProjectName = document.getElementById("field_project_name");
  const fieldBpdNo = document.getElementById("field_bpd_no");
  const fieldLantai = document.getElementById("field_lantai");
  const fieldDate = document.getElementById("field_date");
  const fieldUnitArea = document.getElementById("field_unit_area");

  function showAlert(message, type) {
    uploadAlert.className = `alert alert-${type}`;
    uploadAlert.textContent = message;
    uploadAlert.classList.remove("d-none");
  }

  function hideAlert() {
    uploadAlert.classList.add("d-none");
  }

  function setLoading(isLoading) {
    uploadIcon.classList.toggle("d-none", isLoading);
    uploadSpinner.classList.toggle("d-none", !isLoading);
  }

  function clearTable() {
    tableBody.innerHTML = "";
  }

  function showEmptyState() {
    tableBody.innerHTML = "";
    tableBody.appendChild(emptyRow);
  }

  function isMissing(value) {
    return value === undefined || value === null || String(value).trim() === "";
  }

  function buildRow(rowData, index) {
    const tr = document.createElement("tr");

    const cellNo = document.createElement("td");
    cellNo.className = "text-muted ps-2";
    cellNo.textContent = index + 1;
    tr.appendChild(cellNo);

    // Maps 1:1 to build_result() in app.py, which in turn is derived
    // straight from the CRF labels: ITEM, JOIN, DIM(W/H_L), THICK, QTY.
    const fieldsConfig = [
      { key: "nama_ducting", type: "text" },
      { key: "join_type", type: "text" },
      { key: "w", type: "text" },
      { key: "h", type: "text" },
      { key: "l", type: "text" },
      { key: "bjls", type: "text" },
      { key: "qty", type: "text" },
    ];

    fieldsConfig.forEach((cfg) => {
      const td = document.createElement("td");
      const value = rowData[cfg.key] || "";
      const missing = isMissing(value);

      if (cfg.type === "select") {
        const select = document.createElement("select");
        select.className = "form-select table-input py-1";
        ["TDF", "Slip", "Sisip", "Nek"].forEach((opt) => {
          const optionEl = document.createElement("option");
          optionEl.value = opt;
          optionEl.textContent = opt;
          if (value && value.toUpperCase() === opt.toUpperCase()) {
            optionEl.selected = true;
          }
          select.appendChild(optionEl);
        });
        if (missing) select.classList.add("input-error");
        select.addEventListener("change", () => {
          if (select.value.trim() === "?") {
            select.classList.add("input-error");
          } else {
            select.classList.remove("input-error");
          }
        });
        td.appendChild(select);
      } else {
        const input = document.createElement("input");
        input.type = "text";
        input.className = "table-input" + (missing ? " input-error" : "");
        input.value = missing ? "?" : value;
        input.addEventListener("input", () => {
          if (input.value.trim() === "?") {
            input.classList.add("input-error");
          } else {
            input.classList.remove("input-error");
          }
        });
        td.appendChild(input);
      }

      tr.appendChild(td);
    });

    const actionTd = document.createElement("td");
    actionTd.className = "text-center";
    const trashIcon = document.createElement("i");
    trashIcon.className = "bi bi-trash3-fill action-btn";
    trashIcon.addEventListener("click", () => {
      tr.remove();
      if (!tableBody.querySelector("tr")) {
        showEmptyState();
      }
    });
    actionTd.appendChild(trashIcon);
    tr.appendChild(actionTd);

    return tr;
  }

  function populateResults(data) {
    const header = data.header || {};
    fieldProjectName.value = header.project_name || "";
    fieldBpdNo.value = header.bpd_no || "";
    fieldLantai.value = header.lantai || "";
    fieldDate.value = header.date || "";
    fieldUnitArea.value = header.unit_area || "";

    const rows = data.rows || [];
    clearTable();

    if (rows.length === 0) {
      showEmptyState();
      return;
    }

    rows.forEach((row, idx) => {
      tableBody.appendChild(buildRow(row, idx));
    });
  }

  function resetUI() {
    hideAlert();
    statusBadge.classList.add("d-none");
    if (viewOriginalBtn) {
      viewOriginalBtn.href = "#";
      viewOriginalBtn.classList.add("d-none");
    }
    const saveBtn = document.getElementById("saveBtn");
    if (saveBtn) {
      saveBtn.disabled = true;
    }
    fieldProjectName.value = "";
    fieldBpdNo.value = "";
    fieldLantai.value = "";
    fieldDate.value = "";
    fieldUnitArea.value = "";
    showEmptyState();
  }

  function handleFile(file) {
    if (!file) return;

    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      showAlert("File harus berformat PDF.", "danger");
      return;
    }

    fileChip.style.display = "inline-flex";
    fileChipName.textContent = file.name;
    hideAlert();
    statusBadge.classList.add("d-none");
    setLoading(true);

    const formData = new FormData();
    formData.append("pdf_files", file);

    fetch("/api/upload-bpd", {
      method: "POST",
      body: formData,
    })
      .then((response) => response.json().then((body) => ({ ok: response.ok, body })))
      .then(({ ok, body }) => {
        setLoading(false);
        if (!ok || !body.success) {
          showAlert(body.error || "Gagal memproses file.", "danger");
          showEmptyState();
          return;
        }
        statusBadge.classList.remove("d-none");
        if (viewOriginalBtn && body.filename) {
          viewOriginalBtn.href = `/uploads/${body.filename}`;
          viewOriginalBtn.classList.remove("d-none");
        }
        populateResults(body.data);
        const saveBtn = document.getElementById("saveBtn");
        if (saveBtn) {
          saveBtn.disabled = false;
        }
      })
      .catch((err) => {
        setLoading(false);
        showAlert("Terjadi kesalahan saat mengupload file: " + err.message, "danger");
        showEmptyState();
      });
  }

  uploadLink.addEventListener("click", (e) => {
    e.preventDefault();
    fileInput.click();
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  });

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      fileInput.files = e.dataTransfer.files;
      handleFile(e.dataTransfer.files[0]);
    }
  });

  fileChipRemove.addEventListener("click", () => {
    fileInput.value = "";
    fileChip.style.display = "none";
    resetUI();
  });

  document.getElementById("cancelBtn").addEventListener("click", () => {
    fileInput.value = "";
    fileChip.style.display = "none";
    resetUI();
  });

  document.getElementById("saveBtn").addEventListener("click", () => {
    if (!confirm("Apakah Anda yakin ingin menyimpan data BPD ini?")) {
      return;
    }
    const project_name = fieldProjectName.value.trim();
    const bpd_no = fieldBpdNo.value.trim();
    const lantai = fieldLantai.value.trim();
    const unit_area = fieldUnitArea.value.trim();
    const date = fieldDate.value.trim();

    const rows = [];
    const trs = tableBody.querySelectorAll("tr");
    trs.forEach((tr) => {
      if (tr.id === "emptyRow") return;

      const inputs = tr.querySelectorAll("input, select");
      if (inputs.length >= 7) {
        rows.push({
          nama_ducting: inputs[0].value.trim(),
          join_type: inputs[1].value.trim(),
          w: inputs[2].value.trim(),
          h: inputs[3].value.trim(),
          l: inputs[4].value.trim(),
          bjls: inputs[5].value.trim(),
          qty: inputs[6].value.trim()
        });
      }
    });

    if (rows.length === 0) {
      showAlert("Tidak ada data tabel untuk disimpan.", "warning");
      return;
    }

    const saveBtn = document.getElementById("saveBtn");
    const originalText = saveBtn.innerHTML;
    saveBtn.disabled = true;
    saveBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Saving...`;

    fetch("/api/save-bpd", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        project_name,
        bpd_no,
        lantai,
        unit_area,
        date,
        rows
      })
    })
      .then((res) => res.json())
      .then((body) => {
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalText;
        if (body.success) {
          alert("BPD berhasil disimpan");
          showAlert("BPD berhasil disimpan", "success");
          fileInput.value = "";
          fileChip.style.display = "none";
          resetUI();
        } else {
          showAlert(body.error || "Gagal menyimpan data.", "danger");
        }
      })
      .catch((err) => {
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalText;
        showAlert("Terjadi kesalahan saat menyimpan data: " + err.message, "danger");
      });
  });

  // Initialize empty state on page load
  showEmptyState();
});