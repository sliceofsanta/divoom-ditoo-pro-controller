"""The team scene must retain the user's chosen original working design."""
import unittest
from clawd_faces import (BG, SCREEN, FACES, STEEL, CYAN, CREAM, RED, MINT, BODY,
                         clawd, laptop, blank, px, working_frames, workstation_frames)

DESK_STATES = ("working", "delegating", "terminal", "thinking", "reviewing",
               "alerting", "alerting2", "alerting3", "alert-permission",
               "alert-question", "alert-plan", "success", "done", "taskdone",
               "error", "chilling")


def screen(frame):
    return tuple(tuple(row[8:14]) for row in frame[10:13])


def without_cursor(frame):
    return tuple(tuple(SCREEN if c == CREAM else c for c in row) for row in screen(frame))


class WorkstationTests(unittest.TestCase):
    def test_workstation_is_long_native_and_overlay_safe(self):
        frames, delays = workstation_frames()
        self.assertEqual(len(frames), 120)
        self.assertEqual(sum(delays), 24000)
        self.assertEqual(FACES["delegating"][0], workstation_frames)
        for frame in frames:
            self.assertEqual(len(frame), 16)
            self.assertTrue(all(len(row) == 16 for row in frame))
            self.assertTrue(all(c == BG for c in frame[0] + frame[15]))
        self.assertEqual(frames[0], frames[-1])

    def test_original_working_pose_and_laptop_are_preserved(self):
        frames, _ = workstation_frames()
        original = blank(BG)
        clawd(original, y=4, gaze=1, arms="hug", step=1)
        laptop(original)
        px(original, 5, 12, BODY)
        px(original, 6, 12, BODY)
        self.assertEqual(frames[0], original)
        self.assertEqual(frames, working_frames()[0])
        for frame in frames:
            self.assertEqual(frame[9][7:15], [STEEL]*8)
            self.assertEqual(frame[14][5:16], [STEEL]*11)
            # Same Clawd + laptop with small gestures, not a scene switch.
            changed = sum(a != b for y, (row, ref) in enumerate(zip(frame, original))
                          for x, (a,b) in enumerate(zip(row,ref))
                          if not (8 <= x <= 13 and 10 <= y <= 12))
            self.assertLessEqual(changed, 20)
        self.assertNotEqual(frames[0], frames[1])
        self.assertNotEqual(frames[0], frames[17])

    def test_every_desk_state_preserves_bezel_and_overlay_rows(self):
        for name in DESK_STATES:
            frames, delays = FACES[name][0]()
            self.assertEqual(len(frames), len(delays), name)
            for frame in frames:
                self.assertEqual(len(frame), 16, name)
                self.assertTrue(all(len(row) == 16 for row in frame), name)
                self.assertEqual(frame[9][7:15], [STEEL]*8, name)
                self.assertEqual(frame[14][5:16], [STEEL]*11, name)
                self.assertTrue(all(c == BG for c in frame[0] + frame[15]), name)

    def test_terminal_types_scrolls_and_freezes_for_reading(self):
        frames, _ = workstation_frames()
        self.assertGreater(len({without_cursor(f) for f in frames[:24]}), 4)
        for first, last in ((29,35), (91,97)):
            self.assertEqual(len({without_cursor(f) for f in frames[first:last+1]}), 1)
            self.assertGreater(len({screen(f) for f in frames[first:last+1]}), 1)
            self.assertEqual(len({tuple(f[12][5:7] + f[13][5:7])
                                  for f in frames[first:last+1]}), 1)
        for name in ("thinking", "reviewing"):
            reading, _ = FACES[name][0]()
            self.assertEqual(len({without_cursor(f) for f in reading}), 1)
            self.assertEqual(len({screen(f) for f in reading}), 2)

    def test_outcomes_are_persistent_and_never_faked_during_work(self):
        for name in ("working", "delegating", "thinking", "reviewing", "terminal"):
            for frame in FACES[name][0]()[0]:
                self.assertFalse(any(c in (MINT, RED) for row in screen(frame) for c in row), name)
        for name, color, points in (
            ("error", RED, ((9,10), (11,10), (10,11), (9,12), (11,12))),
            ("done", MINT, ((9,11), (10,12), (11,11), (12,10))),
            ("taskdone", MINT, ((9,11), (10,12), (11,11), (12,10))),
            ("success", MINT, ((9,11), (10,12), (11,11), (12,10))),
        ):
            frames, delays = FACES[name][0]()
            for frame in frames:
                for x,y in points:
                    self.assertEqual(frame[y][x], color, name)
            if name in ("success", "error"):
                self.assertEqual(sum(delays), 6000)

    def test_waiting_cursor_pulses_without_typing_and_idle_is_dim(self):
        for name in ("alerting", "alerting2", "alerting3", "alert-permission",
                     "alert-question", "alert-plan"):
            frames, _ = FACES[name][0]()
            self.assertEqual(len({screen(f) for f in frames}), 3, name)
            for frame in frames:
                self.assertNotEqual(frame[10][10], BG)
                self.assertFalse(any(c == CYAN for row in screen(frame) for c in row))
        frames, _ = FACES["chilling"][0]()
        self.assertEqual(len({screen(f) for f in frames}), 2)
        self.assertNotEqual(screen(frames[0]), screen(frames[5]))


if __name__ == "__main__":
    unittest.main()
