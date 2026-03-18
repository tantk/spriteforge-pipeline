---
layout: default
title: SpriteForge - Fighting Game Sprite Sheet LoRA
---

# SpriteForge

**A LoRA for swapping characters into fighting game sprite sheets**

Built for the [Qwen-Image LoRA Training Competition](https://modelscope.ai/active/qwenimagelora) on ModelScope.

Base model: Qwen-Image-Edit-2511

---

## The Problem

Consistent multi-frame sprite sheets are hard. AI image models struggle to maintain character consistency across 16 frames in a single 4x4 grid — poses become incoherent, characters change appearance between cells.

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; max-width: 800px;">
  <img src="assets/qwen_nolora_1.png" alt="No LoRA example 1">
  <img src="assets/qwen_nolora_2.png" alt="No LoRA example 2">
  <img src="assets/qwen_nolora_3.png" alt="No LoRA example 3">
  <img src="assets/nolora_4.png" alt="No LoRA example 4">
</div>

*Base Qwen-Image-Edit without LoRA: inconsistent character appearance and incoherent frame sequences*

Manual pixel art gives consistency but takes hours of skilled artist work per sheet. A typical fighting game needs 10+ characters × 10+ animations = 100+ sprite sheets.

---

## The Approach: Template-Based Character Swapping

Instead of asking the model to generate sprite sheets from scratch, we reframe the task as **character replacement** — something image editing models are built for.

The model receives:
1. **A character reference image** — who you want
2. **An existing sprite sheet template** — what animation/poses to use
3. **A simple prompt** — "Replace the character in the sprite sheet with the character from the reference image"

The consistency comes from the template, not the generation. The LoRA refines the base model's character swapping for the specific domain of 4×4 sprite grids — improving frame-to-frame consistency.

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; max-width: 800px;">
  <img src="assets/lora_1.png" alt="LoRA result 1">
  <img src="assets/lora_1.gif" alt="LoRA result 1 animated">
  <img src="assets/lora_2.png" alt="LoRA result 2">
  <img src="assets/lora_2.gif" alt="LoRA result 2 animated">
  <img src="assets/lora_3.png" alt="LoRA result 3">
  <img src="assets/lora_3.gif" alt="LoRA result 3 animated">
  <img src="assets/lora_4.png" alt="LoRA result 4">
  <img src="assets/lora_4.gif" alt="LoRA result 4 animated">
</div>

*With SpriteForge LoRA: consistent character across all 16 frames*

---

## Where Do Templates Come From?

Templates can come from any source — the LoRA doesn't care how the template was made, it just swaps the character. Possible sources include:

- **3D rendering pipelines** (Blender + Mixamo — our approach)
- **Hand-drawn sprite sheets** (draw one character's sheet, reuse as template for others)
- **Existing game assets** (use sprites from your own or open-source games)
- **AI-generated + manually corrected** (generate one good sheet, fix any bad frames, use as template forever)

We demonstrate template generation using a Blender + Mixamo pipeline as a proof of concept:

### Training Data: 7 Characters × 14 Animations

<div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 8px; max-width: 600px;">
  <img src="assets/ref_original.png" alt="Original character">
  <img src="assets/ref_army_man.png" alt="Army man">
  <img src="assets/ref_blackdress_girl.png" alt="Black dress girl">
  <img src="assets/ref_pinkhair_boy.png" alt="Pink hair boy">
</div>

*4 of the 7 training characters (VRoid Studio → Mixamo → Blender)*

14 fighting animations: Idle, Walk, Run+Roll, Left/Right Hook, Hook+Right Hook, Quad Punch, Knee+Roundhouse Kick, Spinning Kick, Fall+Get Up, Armada, Hit+Block, Left/Right Kick, Knees to Uppercut, Punch Elbow Combo, and a 360° Northern Soul Spin.

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; max-width: 600px;">
  <img src="assets/sheet_army_idle.png" alt="Idle + Walk">
  <img src="assets/sheet_blackdress_hook.png" alt="Left Right Hook">
  <img src="assets/sheet_bluedress_kick.png" alt="Spinning Kick">
  <img src="assets/sheet_greenhair_armada.png" alt="Armada">
</div>

### 360° Spin Sheet

The Northern Soul Spin captures the character from all angles — each frame shows a different rotation.

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; max-width: 500px;">
  <img src="assets/sheet_spin.png" alt="Spin sheet">
  <img src="assets/spin_preview.gif" alt="Spin preview GIF">
</div>

---

## Generalization

The LoRA generalizes to a range of characters and animations not in the training data.

### Unseen Art Styles

Tested with art styles not present in training (training data was exclusively 3D-rendered VRoid characters):

<img src="assets/lora_3d_unseen.png" alt="Unseen character style" style="max-width: 500px;">

### Unseen Animations

Template sprite sheets from animations the model never saw during training still produce consistent results:

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; max-width: 600px;">
  <img src="assets/unseen_hurricane.png" alt="Hurricane Kick (unseen)">
  <img src="assets/unseen_breakdance.png" alt="Breakdance (unseen)">
</div>

<img src="assets/hurricane_kick_preview.gif" alt="Hurricane Kick GIF" style="max-width: 256px;">

*Hurricane Kick — an animation not in the training data*

---

## What Worked and What Didn't

### Iteration 1: Generate from Scratch ❌

Single input (character reference) → model generates sprite sheet. The model learned to produce 4x4 grids but couldn't maintain coherent frame-to-frame animation. An image **editing** model shouldn't be asked to **generate** complex structured outputs from scratch.

### Iteration 2: Detailed Per-Frame Prompts ❌

Same approach but with 600+ character prompts describing each of the 16 frames individually. No improvement — LoRA doesn't have enough capacity for conditional per-frame spatial generation from text.

### Iteration 3: Character Swap ✅

Multi-image input: character reference + existing sprite sheet template → swap the character. This works because it leverages the model's core strength (image editing) and provides the layout as input rather than asking the model to learn it.

---

## Model Architecture & Technical Details

### Architecture

LoRA fine-tuned on **Qwen-Image-Edit-2511** using ModelScope Civision. Multi-image input format: the model receives a character reference image and an existing sprite sheet template, then outputs a new sprite sheet with the reference character swapped in while preserving all poses and frame layout. 100 training pairs with random template character mixing to prevent overfitting to specific character pairings.

The base Qwen-Image-Edit model already handles character replacement well, but produces occasional inconsistencies in multi-frame layouts. The LoRA refines this for the specific domain of 4×4 sprite grids.

### Template Generation Pipeline

We demonstrate one approach to template creation using a 3D rendering pipeline:

```
VRoid Studio → VRM characters
    → Mixamo auto-rig + 25 animations
        → Blender retarget + GPU render
            → 1024×1024 sprite sheets + character references
                → Training pairs with random template mixing
```

This is a proof of concept — templates can come from any source that produces consistent multi-frame sprite sheets.

### Training Details

- **Base model:** Qwen-Image-Edit-2511
- **Training pairs:** 100 (multi-image: reference + template → output)
- **Prompt:** "Replace the character in the sprite sheet with the character from the reference image"
- **Epochs:** 10
- **Repeat:** 5
- **Checkpoint used:** 10
- **Trigger word:** None
- **All other parameters:** Default (ModelScope Civision)
- **Platform:** ModelScope Civision
- **Note:** Inference requires ~40GB VRAM. Free inference is available on ModelScope.

### Training Parameters

<img src="assets/parameters.png" alt="Training parameters" style="max-width: 300px;">

### Training Loss

<img src="assets/loss.png" alt="Training loss curve" style="max-width: 600px;">

Loss is still decreasing at epoch 10 with no sign of plateau — the model could benefit from additional training epochs.

---

## Application

**For creators who have 2D character designs but need game-ready sprite sheets — without creating 3D models.**

1. Pick a sprite sheet template from the curated library (or use your own)
2. Provide your character reference image (any style — sketch, pixel art, concept art, photo)
3. Get a consistent 16-frame sprite sheet in seconds

The approach avoids the multi-frame consistency problem entirely by separating **animation structure** (from the template) from **character identity** (from the reference image).

---

## Future Work

The spin animation training data includes per-frame orientation angles in the prompts. A natural extension is training with cross-angle pairs — where the template and output show different camera angles — enabling prompt-controlled character rotation. This would allow users to specify viewing angles per frame, moving toward 3D-aware sprite generation from 2D inputs.

---

## Links

- **Model:** [SpriteForge on ModelScope](https://modelscope.ai/models/tantk7/spriteforgev3)
- **Resources:** [Character references + sprite sheet templates on itch.io](#)
- **Competition:** [Qwen-Image LoRA Training Competition](https://modelscope.ai/active/qwenimagelora)

---

*Built with Blender 5.0, VRoid Studio, Mixamo, and Claude Code.*

[Read the full development blog →](blog)
