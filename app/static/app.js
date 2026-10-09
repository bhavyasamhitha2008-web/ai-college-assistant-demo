const studentSelect = document.querySelector("#student-id");
const studentForm = document.querySelector("#student-form");
const attendanceElement = document.querySelector("#attendance");
const questionForm = document.querySelector("#question-form");
const answerElement = document.querySelector("#answer");
const statusElement = document.querySelector("#status");

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error?.message || "The request could not be completed.");
  }
  return payload;
}

async function loadAttendance(event) {
  event.preventDefault();
  statusElement.textContent = "";
  attendanceElement.textContent = "Loading…";

  try {
    const studentId = studentSelect.value.trim();
    const result = await requestJson("/api/attendance", {
      headers: { "X-Demo-Student-ID": studentId },
    });
    attendanceElement.replaceChildren();
    if (result.subjects.length === 0) {
      attendanceElement.textContent = "No subjects are recorded for this student.";
      return;
    }
    for (const subject of result.subjects) {
      const card = document.createElement("article");
      card.className = "subject-result";
      const title = document.createElement("h3");
      title.textContent = `${subject.course_code} — ${subject.subject}`;
      const details = document.createElement("p");
      const percentage = subject.percentage === null
        ? "No classes recorded"
        : `${subject.percentage}%`;
      details.textContent =
        `${subject.attended_classes} attended out of ${subject.total_classes} classes (${percentage})`;
      card.append(title, details);
      attendanceElement.append(card);
    }
  } catch (error) {
    attendanceElement.textContent = "Could not load attendance.";
    statusElement.textContent = error.message;
  }
}

studentForm.addEventListener("submit", loadAttendance);
questionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  answerElement.textContent = "Searching…";
  try {
    const question = new FormData(questionForm).get("question");
    const result = await requestJson(`/api/ask?q=${encodeURIComponent(question)}`);
    answerElement.replaceChildren();
    const responseText = document.createElement("p");
    responseText.textContent = result.answer;
    answerElement.append(responseText);
    if (result.source) {
      const source = document.createElement("p");
      source.className = "source";
      source.textContent = `Source: ${result.source}`;
      answerElement.append(source);
    }
  } catch (error) {
    answerElement.textContent = error.message;
  }
});

studentForm.requestSubmit();
