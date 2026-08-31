// app.js — Part II: JavaScript validation, JSON handling, and submission tracking
// DATA-260 HW1 — Campus Course Catalogue & Enrolment

(() => {
  const form = document.getElementById('courseForm');

  // II.1 — Arrow function validating the content field length and the terms checkbox.
  const validateForm = (data) => {
    if (data.description.trim().length <= 25) {
      alert('Course description must be longer than 25 characters. Please add more detail.');
      return false;
    }
    if (!data.agreeTerms) {
      alert('You must agree to the terms and conditions before submitting.');
      return false;
    }
    return true;
  };

  // II.5 — Closure tracking how many times the form has been successfully submitted.
  const createSubmissionCounter = () => {
    let count = 0;
    return () => {
      count += 1;
      return count;
    };
  };
  const countSubmission = createSubmissionCounter();

  form.addEventListener('submit', (event) => {
    event.preventDefault();

    const formData = {
      courseCode: form.courseCode.value.trim(),
      courseTitle: form.courseTitle.value.trim(),
      submitterEmail: form.submitterEmail.value.trim(),
      description: form.description.value.trim(),
      department: form.department.value,
      agreeTerms: form.agreeTerms.checked,
    };

    if (!validateForm(formData)) {
      return;
    }

    // II.2 — Convert the form data into a JSON string and log it.
    const jsonString = JSON.stringify(formData);
    console.log('Form submitted as JSON:', jsonString);

    const parsed = JSON.parse(jsonString);

    // II.3 — Object destructuring to pull out the primary field and email.
    const { courseCode, submitterEmail } = parsed;
    console.log('Primary field (courseCode):', courseCode);
    console.log('Submitter email:', submitterEmail);

    // II.4 — Spread operator to add submissionDate to the parsed object.
    const finalRecord = { ...parsed, submissionDate: new Date().toISOString() };
    console.log('Final record with submissionDate:', finalRecord);

    // II.5 — Log the running submission count via the closure above.
    const submissionCount = countSubmission();
    console.log(`Submission count: ${submissionCount}`);

    alert(`Course "${courseCode}" submitted successfully! (Submission #${submissionCount})`);
    form.reset();
    form.courseCode.focus();
  });
})();
