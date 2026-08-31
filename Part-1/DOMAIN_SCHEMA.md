# Domain Schema — Campus Course Catalogue and Enrolment

**DOMAIN_ID:** 0
**Assigned Domain:** Campus course catalogue and enrolment
**Entity:** `Course` — a single course listing submitted into the catalogue.

## Fields

| Field            | Type              | Required | Description                                                                 |
|------------------|-------------------|----------|-------------------------------------------------------------------------------|
| `courseCode`     | string (primary)  | yes      | Unique course identifier, format `DEPT-###` (e.g. `DATA-260`).               |
| `courseTitle`    | string (secondary)| yes      | Human-readable course name (e.g. "Big Data Technologies and Systems").       |
| `submitterEmail` | string (email)    | yes      | Email of the person submitting/proposing the listing.                        |
| `description`    | text              | yes      | Course description: topics covered, learning outcomes, format. Min 25 chars. |
| `department`     | enum (category)   | yes      | One of the four category values below.                                       |
| `credits`        | integer           | no       | Number of units the course carries (not collected in the HW1 form).          |
| `instructor`      | string            | no       | Instructor of record (not collected in the HW1 form).                        |
| `semester`       | string            | no       | Offering term, e.g. "Fall 2026" (not collected in the HW1 form).             |
| `capacity`       | integer           | no       | Maximum enrolment seats (not collected in the HW1 form).                     |
| `enrolledCount`  | integer           | no       | Current number of enrolled students (not collected in the HW1 form).         |
| `prerequisites`  | string            | no       | Comma-separated prerequisite course codes (not collected in the HW1 form).   |
| `agreeTerms`     | boolean           | yes      | Whether the submitter agreed to the terms and conditions.                    |
| `submissionDate` | ISO 8601 datetime | derived  | Added client-side (via spread operator) at the moment of successful submit.  |
| `status`         | enum              | no       | `pending` \| `approved` \| `rejected` (not collected in the HW1 form).       |

The HW1 form (Part I) collects the required subset needed for a minimal catalogue
submission: `courseCode`, `courseTitle`, `submitterEmail`, `description`,
`department`, `agreeTerms`. The remaining fields describe the fuller entity as it
would exist in a real course-catalogue system and may be used in later homeworks.

## Category Values — `department` (dropdown)

1. `Computer Science`
2. `Data Science & AI`
3. `Business Analytics`
4. `Engineering`

## Category Values — `status` (not in HW1 form, reserved for later homeworks)

1. `pending`
2. `approved`
3. `rejected`
