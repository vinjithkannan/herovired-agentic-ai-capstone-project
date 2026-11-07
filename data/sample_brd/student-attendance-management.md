# Business Requirements Document
## Student Attendance Management System

**Document ID:** BRD-ATT-001  
**Version:** 1.0  
**Status:** Synthetic capstone demonstration data

## 1. Business objective
The university needs centralized attendance management for faculty, students and administrators, reducing manual registers and improving attendance visibility.

## 2. Stakeholders
- Faculty member
- Student
- Department administrator
- University administrator

## 3. Functional requirements
- **FR-001 — Mark attendance:** Faculty can record attendance for students enrolled in a course they are assigned to teach.
- **FR-002 — View attendance:** Students can view their attendance records and percentage for each enrolled course.
- **FR-003 — Attendance reports:** Department administrators can generate reports by department, course, semester and date range.
- **FR-004 — Course and semester context:** Attendance records must be associated with the correct course, semester and academic year.
- **FR-005 — Attendance correction:** Authorized roles can correct attendance while preserving an audit trail. The approval policy needs clarification.

## 4. Non-functional requirements
- **NFR-001 — Access control:** Users access only information permitted by their role and scope.
- **NFR-002 — Auditability:** Attendance creation and correction actions are auditable.
- **NFR-003 — Availability:** Available during normal university operating hours; formal target unspecified.
- **NFR-004 — Performance:** Attendance lists and reports return within an acceptable response time; target unspecified.

## 5. Business rules
- Faculty can mark attendance only for assigned courses.
- Students can view only their own attendance.
- Administrators can view reports within their authorized scope.
- Corrections preserve an audit trail.

## 6. Open questions
1. Which attendance statuses are supported (Present, Absent, Late, Excused)?
2. Can faculty edit attendance after submission?
3. Is administrator approval required for corrections?
4. What is the minimum attendance percentage for eligibility?
5. What are peak concurrent users and report response-time targets?
6. Is offline attendance capture required?

## 7. Out of scope
Biometric attendance, GPS attendance, parent notifications and fee management.
