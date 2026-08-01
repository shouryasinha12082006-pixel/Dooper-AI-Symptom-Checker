// Dooper AI Symptom Checker - Main Javascript File

// 1. Voice Input (Speech Recognition)
function startVoiceInput(targetId) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        alert("Your browser does not support Speech Recognition. Please try Chrome or Safari.");
        return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    const micBtn = document.getElementById("micBtn");
    const targetInput = document.getElementById(targetId);

    recognition.onstart = function() {
        micBtn.classList.add("listening");
        micBtn.innerHTML = '<i class="fa-solid fa-microphone-lines"></i>';
    };

    recognition.onerror = function(event) {
        console.error("Speech recognition error", event.error);
        micBtn.classList.remove("listening");
        micBtn.innerHTML = '<i class="fa-solid fa-microphone"></i>';
    };

    recognition.onend = function() {
        micBtn.classList.remove("listening");
        micBtn.innerHTML = '<i class="fa-solid fa-microphone"></i>';
    };

    recognition.onresult = function(event) {
        const speechResult = event.results[0][0].transcript;
        if (targetInput.value) {
            targetInput.value += " " + speechResult;
        } else {
            targetInput.value = speechResult;
        }
    };

    recognition.start();
}

// 2. Client-side PDF Generation (using jsPDF)
function loadScript(url, callback) {
    const script = document.createElement("script");
    script.type = "text/javascript";
    script.src = url;
    script.onload = callback;
    document.head.appendChild(script);
}

function exportAssessmentToPDF(assessmentData) {
    const jspdfUrl = "https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js";
    loadScript(jspdfUrl, function() {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();

        // Colors
        const primaryColor = [227, 6, 19]; // Dooper Red
        const darkColor = [31, 41, 55];
        const greyColor = [107, 114, 128];

        // Draw header bar
        doc.setFillColor(...primaryColor);
        doc.rect(0, 0, 210, 15, "F");

        // Brand Title
        doc.setTextColor(255, 255, 255);
        doc.setFont("Helvetica", "bold");
        doc.setFontSize(16);
        doc.text("DOOPER HEALTH", 15, 10);

        // Document Title
        doc.setTextColor(...darkColor);
        doc.setFontSize(22);
        doc.text("AI Symptom Checker Report", 15, 30);

        // Meta info
        doc.setFont("Helvetica", "normal");
        doc.setFontSize(10);
        doc.setTextColor(...greyColor);
        doc.text(`Report Date: ${assessmentData.date}`, 15, 38);
        doc.text(`Patient Name: ${assessmentData.userName}`, 15, 43);
        doc.text(`Profile Details: Age ${assessmentData.age}, Gender ${assessmentData.gender}, Weight ${assessmentData.weight}kg, Height ${assessmentData.height}cm, Pain ${assessmentData.painLevel}/10${assessmentData.temperature && assessmentData.temperature !== 'N/A' ? ', Temp ' + assessmentData.temperature + '°' + (assessmentData.temperatureUnit || 'F') : ''}`, 15, 48);

        // Line separator
        doc.setDrawColor(229, 231, 235);
        doc.line(15, 53, 195, 53);

        // User Symptoms
        doc.setTextColor(...darkColor);
        doc.setFont("Helvetica", "bold");
        doc.setFontSize(12);
        doc.text("Symptoms Reported:", 15, 62);
        doc.setFont("Helvetica", "normal");
        doc.setFontSize(11);
        const symptomsLines = doc.splitTextToSize(assessmentData.symptoms, 180);
        doc.text(symptomsLines, 15, 68);

        let currentY = 68 + (symptomsLines.length * 6);

        // Medical Assessment
        doc.setFont("Helvetica", "bold");
        doc.setFontSize(12);
        doc.text("AI Health Assessment Findings:", 15, currentY);
        currentY += 6;

        // Condition
        doc.setFont("Helvetica", "normal");
        doc.setFontSize(11);
        doc.text(`Possible Condition: ${assessmentData.condition}`, 15, currentY);
        currentY += 6;

        // Severity
        doc.text(`Severity Level: ${assessmentData.severity}`, 15, currentY);
        currentY += 6;

        // Specialty
        doc.text(`Recommended Medical Specialty: ${assessmentData.specialty}`, 15, currentY);
        currentY += 10;

        // Explanation
        doc.setFont("Helvetica", "bold");
        doc.text("Short Explanation:", 15, currentY);
        currentY += 6;
        doc.setFont("Helvetica", "normal");
        const explanationLines = doc.splitTextToSize(assessmentData.explanation, 180);
        doc.text(explanationLines, 15, currentY);
        currentY += (explanationLines.length * 6) + 4;

        // Self-care advice
        doc.setFont("Helvetica", "bold");
        doc.text("Health Advice & Recommendations:", 15, currentY);
        currentY += 6;
        doc.setFont("Helvetica", "normal");
        const adviceLines = doc.splitTextToSize(assessmentData.advice, 180);
        doc.text(adviceLines, 15, currentY);
        currentY += (adviceLines.length * 6) + 12;

        // Disclaimer Box
        doc.setFillColor(253, 242, 242);
        doc.rect(15, currentY, 180, 20, "F");
        doc.setDrawColor(...primaryColor);
        doc.line(15, currentY, 15, currentY + 20);

        doc.setTextColor(...primaryColor);
        doc.setFont("Helvetica", "bold");
        doc.setFontSize(9);
        doc.text("MEDICAL DISCLAIMER:", 20, currentY + 6);
        doc.setFont("Helvetica", "normal");
        const disclaimerLines = doc.splitTextToSize("This assessment is AI-generated and is not a medical diagnosis. Please consult a qualified doctor for professional medical advice.", 170);
        doc.text(disclaimerLines, 20, currentY + 11);

        // Save PDF
        doc.save(`Dooper_Assessment_${assessmentData.id}.pdf`);
    });
}

// 3. AI Chat Assistant functionality
function initChatAssistant(assessmentId) {
    const chatForm = document.getElementById("chatForm");
    const chatInput = document.getElementById("chatInput");
    const chatMessages = document.getElementById("chatMessages");

    if (!chatForm || !chatInput || !chatMessages) return;

    chatForm.addEventListener("submit", function(e) {
        e.preventDefault();
        const messageText = chatInput.value.trim();
        if (!messageText) return;

        // Add user bubble
        appendChatBubble("user", messageText);
        chatInput.value = "";

        // Add typing/thinking bubble
        const typingId = appendChatBubble("doctor", '<i class="fa-solid fa-circle-notch fa-spin"></i> Typing...');

        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Post message to backend
        fetch(`/assessment/${assessmentId}/chat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ message: messageText })
        })
        .then(response => response.json())
        .then(data => {
            // Remove typing bubble
            const typingBubble = document.getElementById(typingId);
            if (typingBubble) typingBubble.remove();

            if (data.status === "success") {
                appendChatBubble("doctor", data.reply);
            } else {
                appendChatBubble("doctor", "Sorry, I encountered an error. Please try again.");
            }
            chatMessages.scrollTop = chatMessages.scrollHeight;
        })
        .catch(err => {
            console.error(err);
            const typingBubble = document.getElementById(typingId);
            if (typingBubble) typingBubble.remove();
            appendChatBubble("doctor", "Could not connect to the assistant server. Please check your internet connection.");
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    });

    function appendChatBubble(sender, text) {
        const bubble = document.createElement("div");
        const uniqueId = "bubble_" + Math.random().toString(36).substr(2, 9);
        bubble.id = uniqueId;
        bubble.className = `chat-bubble ${sender}`;
        bubble.innerHTML = text;
        chatMessages.appendChild(bubble);
        return uniqueId;
    }
}

// Doctor Appointment Scheduling helper
function bookDoctorAppointment(assessmentId, specialistType, doctorName, dateId, resultDivId) {
    const dateInput = document.getElementById(dateId);
    const resultDiv = document.getElementById(resultDivId);
    
    if (!dateInput || !dateInput.value) {
        if (resultDiv) {
            resultDiv.innerHTML = `<span style="color: var(--danger-color)">Please select a valid date and time.</span>`;
        }
        return;
    }

    const dateVal = dateInput.value.replace('T', ' ');

    fetch('/book-appointment', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            assessment_id: assessmentId,
            specialist_type: specialistType,
            doctor_name: doctorName,
            appointment_date: dateVal
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'success') {
            if (resultDiv) {
                resultDiv.innerHTML = `<span style="color: var(--success-color)"><i class="fa-solid fa-circle-check"></i> ${data.message}</span>`;
            }
            dateInput.disabled = true;
            const btn = dateInput.nextElementSibling;
            if (btn) btn.disabled = true;
        } else {
            if (resultDiv) {
                resultDiv.innerHTML = `<span style="color: var(--danger-color)">Error: ${data.message}</span>`;
            }
        }
    });
}

function startVoiceRecognition(targetId) {
    startVoiceInput(targetId);
}
