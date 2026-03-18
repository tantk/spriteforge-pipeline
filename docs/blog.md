---
layout: default
title: Blog - Building SpriteForge
---

# SpriteForge: Building a Character Swap LoRA for Fighting Game Sprite Sheets

*A journey through 3 iterations of training data design for the Qwen-Image LoRA Competition*

---

## The Goal

Train a LoRA on Qwen-Image-Edit that helps indie game developers create fighting game sprite sheets. Given a character image, produce a 4x4 grid of 16 animation frames — punches, kicks, falls, spins — ready to drop into a game engine.

## What We Built

A fully automated pipeline: VRoid Studio characters → Mixamo animations → Blender retarget + render → 1024x1024 sprite sheets → LoRA training pairs. 9 characters, 16 animation types, 100 training pairs.

---

## Iteration 1: Generate Sprite Sheets from Scratch

**Approach:** Single input (character reference image) → model generates a 4x4 sprite sheet.

**Training data:**
- Input: 1024x1024 idle character frame
- Output: 1024x1024 sprite sheet (16 animation frames)
- Prompt: describes the action sequence

**What happened:** Early checkpoints followed the training data — the model learned to produce 4x4 grids with the right character. But by checkpoint 10-15, the outputs became incoherent. The character was recognizable, the grid layout was there, but the 16 frames showed random poses instead of a coherent animation sequence.

**Why it failed:** We were asking an image *editing* model to do image *generation*. Qwen-Image-Edit is designed to transform input images, not create complex structured outputs from scratch. A 4x4 sprite sheet with coherent frame-to-frame animation is an incredibly specific spatial pattern. 100 training pairs wasn't enough for the model to learn both "what a sprite sheet looks like" AND "what each frame should contain."

**Lesson:** Don't fight the model's architecture. An editing model should edit, not generate.

---

## Iteration 2: Detailed Per-Frame Prompts

**Approach:** Same as Iteration 1, but with much more detailed prompts describing each frame individually.

**Training data:**
- Same images as Iteration 1
- Prompt changed from "a fighter performing a kick" to "Frame 1: fighting stance. Frame 2: stepping forward. Frame 3: leg chambering. Frame 4: kick at full extension..."

**What happened:** No meaningful improvement. The model still produced incoherent frame sequences at later checkpoints.

**Why it failed:** LoRA doesn't have enough capacity to learn conditional per-frame spatial generation from text. The model can't parse "Frame 7 should show X at position row 2 column 3." Research also showed that longer, more complex prompts cause the base model to dominate over the LoRA, reducing its influence.

**Lesson:** You can't solve a training data structure problem with better prompts. If the model can't learn the pattern from the images, adding more text won't help.

---

## Iteration 3: Character Swap (What Worked)

**Approach:** Multi-image input. Give the model a character reference AND an existing sprite sheet as template. The model's job: swap the character in the template while keeping all poses intact.

**Training data (3 images per pair):**
- Input 1 (`_start_1`): Character A reference image
- Input 2 (`_start_2`): Character B's sprite sheet (template)
- Output (`_end`): Character A's sprite sheet (same poses as template)
- Prompt: "Replace the character in the sprite sheet with the character from the reference image"

**Template mixing:** Each pair randomly selects a different character's sprite sheet as the template. This prevents the model from memorizing specific character pairings and forces it to learn the general swap rule.

**What happened:** It worked. The model successfully swaps characters in sprite sheets — and generalizes to characters outside the training data, including different art styles (pixel art, anime, realistic).

**Why it worked:**
1. **Leverages the model's strength.** Qwen-Image-Edit is built for image editing. "Replace character A with character B" is exactly what it's designed to do.
2. **The template provides structure.** The model doesn't need to learn sprite sheet layout — it's given the layout in the input. It just needs to learn the swap operation.
3. **The task is simple.** One clear instruction, one consistent operation. The LoRA learns a tight, focused transformation.
4. **The base model was already 90% there.** Before any LoRA training, the base Qwen-Image-Edit could already swap characters with only 1-2 frames going wrong. The LoRA just cleaned up the remaining errors.

---

## Technical Challenges Along the Way

### The Retarget Saga

Getting Mixamo animations onto different VRoid characters required Blender's Retarget addon for constraint-based visual baking. What should have been straightforward turned into a multi-hour debugging session:

- **Root motion re-add broke everything.** An earlier iteration of the export script zeroed the FBX armature transform and re-added root motion fcurves. This produced deformed animations for all characters except the first one tested. The fix: don't touch the FBX transform at all. Let the visual bake capture everything naturally.

- **One sheet was the exception.** Sheet 08 (Fall + Get Up) required `armature_z_override` which depends on Mixamo root motion being preserved as object-level fcurves. This needed the zeroing + root motion approach. Solution: dual export mode — simple for 12 sheets, root_motion for sheet 08, auto-detected from config.

- **Conflicting documentation.** Two memory files gave opposite advice about root motion handling. One said "DO NOT copy root motion," the other said "you MUST re-add root motion." Both were written by AI agents in different conversations, each solving a different aspect of the problem. The conflict caused repeated regressions.

**Lesson:** When solving complex multi-step problems with AI agents across multiple sessions, documentation conflicts are inevitable. Always verify against the actual working output, not just the docs.

### GPU vs CPU Rendering

EEVEE (Blender's real-time renderer) needs GPU access. The `--background` flag disables GPU, forcing CPU software rasterization — 2x slower. Solution: launch Blender with `start /min` (minimized window) instead of `--background` to keep GPU access. Render time dropped from ~2.5 min/sheet to ~1.2 min/sheet.

### The 100-Pair Limit

ModelScope Civision allows max 100 training pairs (300 images in multi-image mode = 100 sets of 3). With 7 characters and 16 animation types, we had to be strategic:
- 7 main characters × 14 sheets = 98 pairs
- 2 extra characters × 1 spin sheet each = 2 pairs
- Total: exactly 100

### Spin Sheets for 3D Reconstruction

The Northern Soul Spin animation naturally rotates the character through 360 degrees. We created 3 variants with different frame selections to maximize angle coverage. Each frame's rotation angle (in degrees) was included in the prompt, potentially enabling users to request specific orientations.

---

## The Pipeline

```
VRoid Studio → VRM characters (9 total)
    → Mixamo auto-rig + 25 animations
        → Blender retarget + export (retarget_export.py)
            → GPU render (batch_render_characters.py)
                → 1024x1024 sprite sheets + character references
                    → Package 100 multi-image pairs
                        → ModelScope Civision LoRA training
```

**Total render time:** ~3 hours for 114 sprite sheets + 9 character references
**Training:** Qwen-Image-Edit-2511, 5 repeats, 100 pairs
**Result:** Character swap LoRA that generalizes to unseen characters and art styles

---

## Key Takeaways

1. **Work with your model, not against it.** An editing model should edit. Don't ask it to generate complex structured outputs from scratch.

2. **Give the model what it needs in the input, not the prompt.** The sprite sheet template provides the layout and poses. The prompt just says "swap the character." Simple inputs + simple prompts > complex prompts.

3. **Start with what the base model can already do.** If the base model can swap characters at 90% accuracy, a LoRA only needs to fix the remaining 10%. That's a much easier learning target than teaching a new capability from zero.

4. **100 pairs is enough when the task is focused.** We wasted time trying to make the model learn everything (layout + animation + character identity). When we narrowed the task to just character swapping, 100 pairs was more than sufficient.

5. **Document aggressively, but verify against reality.** AI agents across multiple sessions will create conflicting documentation. The code and rendered output are the source of truth, not the docs.
