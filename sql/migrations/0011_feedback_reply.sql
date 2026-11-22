-- 0011: replies to in-app feedback (الرد على الملاحظات).
--   An admin answers a note and sets its status (new / in_progress / done); the author
--   sees the answer and may edit the note while it is still new.
-- Rollback: sql/fixes/rollback_0011_feedback_reply.sql

ALTER TABLE `feedback`
  ADD COLUMN `status` varchar(16) NOT NULL DEFAULT 'new' AFTER `app_version`,
  ADD COLUMN `reply` text NULL AFTER `status`,
  ADD COLUMN `replied_by` int(11) DEFAULT NULL AFTER `reply`,
  ADD COLUMN `replied_at` timestamp NULL DEFAULT NULL AFTER `replied_by`,
  ADD COLUMN `edited_at` timestamp NULL DEFAULT NULL AFTER `replied_at`;
