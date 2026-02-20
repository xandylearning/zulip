# Media Message Types - Future Enhancements

This document outlines planned enhancements and extensions for Zulip's rich media message types system. These features are currently stubbed or partially implemented and represent future work.

## Table of Contents

1. [Map UI for Location Picker](#map-ui-for-location-picker)
2. [Enhanced Contact Picker](#enhanced-contact-picker)
3. [Sticker System Enhancements](#sticker-system-enhancements)

---

## Map UI for Location Picker

### Current Implementation

The location picker (`web/src/location_picker.ts`) currently uses the browser's `Geolocation` API to get the user's current location and sends coordinates directly.

### Planned Enhancements

#### 1. Interactive Map Picker

**Goal**: Allow users to select any location on a map, not just their current location.

**Implementation Plan**:

1. **Map Library Integration**
   - Use [Leaflet.js](https://leafletjs.com/) or [Mapbox GL JS](https://docs.mapbox.com/mapbox-gl-js/) for map rendering
   - Create a modal dialog (`web/src/location_picker_modal.ts`)
   - Display map with draggable marker
   - Show address preview as user moves marker

2. **Reverse Geocoding**
   - Integrate with geocoding service (e.g., [Nominatim](https://nominatim.org/), [Mapbox Geocoding API](https://docs.mapbox.com/api/search/geocoding/))
   - Convert coordinates to human-readable address
   - Cache recent addresses to reduce API calls

3. **UI Components**
   - Map container with zoom controls
   - Search bar for address lookup
   - Current location button
   - Address preview panel
   - Confirm/Cancel buttons

**File Structure**:
```
web/src/
  location_picker.ts          # Main entry point (update)
  location_picker_modal.ts    # New: Modal with map UI
  location_map.ts             # New: Map component wrapper
web/styles/
  location_picker_modal.css   # New: Modal styles
  location_map.css            # New: Map styles
```

**Example Implementation**:

```typescript
// web/src/location_picker_modal.ts
import $ from "jquery";
import * as modals from "./modals.ts";

let map: L.Map | null = null;
let marker: L.Marker | null = null;

export function show_location_picker_modal(): Promise<{
    latitude: number;
    longitude: number;
    name: string;
    address?: string;
}> {
    return new Promise((resolve, reject) => {
        const modal = modals.create_modal({
            title: "Share Location",
            body: render_map_modal_body(),
            on_shown: () => {
                initialize_map();
            },
            on_close: () => {
                cleanup_map();
            },
        });

        $("#location-picker-confirm").on("click", () => {
            if (marker) {
                const latlng = marker.getLatLng();
                resolve({
                    latitude: latlng.lat,
                    longitude: latlng.lng,
                    name: $("#location-name").val() as string,
                    address: $("#location-address").val() as string,
                });
                modals.close_modal(modal);
            }
        });

        $("#location-picker-cancel").on("click", () => {
            modals.close_modal(modal);
            reject(new Error("Cancelled"));
        });
    });
}

function initialize_map(): void {
    // Initialize Leaflet map
    map = L.map("location-map-container").setView([40.7128, -74.0060], 13);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map);

    // Add draggable marker
    marker = L.marker([40.7128, -74.0060], {draggable: true}).addTo(map);

    marker.on("dragend", async () => {
        if (marker) {
            const latlng = marker.getLatLng();
            // Reverse geocode to get address
            const address = await reverse_geocode(latlng.lat, latlng.lng);
            $("#location-address").val(address);
        }
    });

    // Get current location button
    $("#location-picker-current").on("click", () => {
        navigator.geolocation.getCurrentPosition((position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            map?.setView([lat, lng], 15);
            marker?.setLatLng([lat, lng]);
        });
    });
}

async function reverse_geocode(lat: number, lng: number): Promise<string> {
    // Call Nominatim or Mapbox API
    const response = await fetch(
        `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json`
    );
    const data = await response.json();
    return data.display_name || `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
}
```

#### 2. Address Search

**Goal**: Allow users to search for locations by address.

**Implementation**:
- Integrate forward geocoding API
- Search bar with autocomplete
- Recent searches cache
- Popular locations quick-select

#### 3. Location History

**Goal**: Remember recently shared locations.

**Implementation**:
- Store recent locations in browser localStorage
- Display in quick-select panel
- Clear history option

#### 4. Static Map Preview

**Goal**: Show a small map preview in the location message card.

**Implementation**:
- Generate static map image URL (e.g., Mapbox Static Images API)
- Display in `renderLocationCard()` in `media_message_card.ts`
- Fallback to coordinates if image unavailable

**Files to Update**:
- `web/src/location_picker.ts` - Integrate modal
- `web/src/media_message_card.ts` - Add map preview
- `web/styles/media_message_card.css` - Style map preview

---

## Enhanced Contact Picker

### Current Implementation

The contact picker (`web/src/contact_picker.ts`) uses simple browser `prompt()` dialogs to collect contact information.

### Planned Enhancements

#### 1. Browser Contacts API Integration

**Goal**: Allow users to select contacts from their device's contact list.

**Implementation Plan**:

1. **Contacts API Integration**
   - Use [Contact Picker API](https://developer.mozilla.org/en-US/docs/Web/API/Contact_Picker_API) (Chrome/Edge)
   - Fallback to manual entry for unsupported browsers
   - Request specific properties (name, email, phone)

2. **Contact Selection UI**
   - Modal with contact list
   - Search/filter contacts
   - Multi-select support (future)
   - Recent contacts quick-select

**Example Implementation**:

```typescript
// web/src/contact_picker.ts (enhanced)

interface ContactData {
    name: string;
    phone?: string;
    email?: string;
    avatar?: string;
}

export async function show_contact_picker(): Promise<ContactData | null> {
    // Check if Contacts API is available
    if ("contacts" in navigator && "select" in navigator.contacts) {
        try {
            const contacts = await navigator.contacts.select(
                ["name", "email", "tel"],
                {multiple: false}
            );
            if (contacts && contacts.length > 0) {
                const contact = contacts[0];
                return {
                    name: contact.name?.[0] || "",
                    phone: contact.tel?.[0] || undefined,
                    email: contact.email?.[0] || undefined,
                };
            }
        } catch (error) {
            // User cancelled or error occurred
            console.error("Contact picker error:", error);
        }
    }

    // Fallback to manual entry modal
    return show_manual_contact_entry();
}

function show_manual_contact_entry(): Promise<ContactData | null> {
    return new Promise((resolve) => {
        const modal = modals.create_modal({
            title: "Share Contact",
            body: render_contact_entry_form(),
            on_shown: () => {
                $("#contact-name-input").focus();
            },
        });

        $("#contact-picker-confirm").on("click", () => {
            const name = $("#contact-name-input").val() as string;
            const phone = $("#contact-phone-input").val() as string;
            const email = $("#contact-email-input").val() as string;

            if (!name || (!phone && !email)) {
                // Show validation error
                return;
            }

            resolve({
                name,
                phone: phone || undefined,
                email: email || undefined,
            });
            modals.close_modal(modal);
        });

        $("#contact-picker-cancel").on("click", () => {
            modals.close_modal(modal);
            resolve(null);
        });
    });
}
```

#### 2. Contact Card UI Enhancement

**Goal**: Improve the display of contact messages with better formatting and actions.

**Implementation**:
- Enhanced contact card layout
- Avatar support (if available)
- Click-to-call/email buttons
- Copy contact info button
- Add to device contacts button (mobile)

**Files to Update**:
- `web/src/media_message_card.ts` - Enhance `renderContactCard()`
- `web/styles/media_message_card.css` - Style contact card

**Example Enhanced Contact Card**:

```typescript
export function renderContactCard(message: Message): string {
    const metadata = message.media_metadata;
    const name = metadata.name as string;
    const phone = metadata.phone as string | undefined;
    const email = metadata.email as string | undefined;

    return `
        <div class="media-contact-card">
            <div class="contact-avatar">
                ${name.charAt(0).toUpperCase()}
            </div>
            <div class="contact-info">
                <div class="contact-name">${escapeHtml(name)}</div>
                ${phone ? `
                    <div class="contact-phone">
                        <a href="tel:${escapeHtml(phone)}">${escapeHtml(phone)}</a>
                        <button class="copy-contact-info" data-value="${escapeHtml(phone)}">
                            Copy
                        </button>
                    </div>
                ` : ""}
                ${email ? `
                    <div class="contact-email">
                        <a href="mailto:${escapeHtml(email)}">${escapeHtml(email)}</a>
                        <button class="copy-contact-info" data-value="${escapeHtml(email)}">
                            Copy
                        </button>
                    </div>
                ` : ""}
            </div>
            <div class="contact-actions">
                ${phone ? `<button class="contact-action-call" data-phone="${escapeHtml(phone)}">Call</button>` : ""}
                ${email ? `<button class="contact-action-email" data-email="${escapeHtml(email)}">Email</button>` : ""}
            </div>
        </div>
        ${getCaptionHtml(message.caption)}
    `;
}
```

#### 3. Contact Import/Export

**Goal**: Allow importing contacts from vCard files and exporting shared contacts.

**Implementation**:
- vCard parser for import
- vCard generator for export
- Bulk contact sharing (future)

#### 4. Contact Validation

**Goal**: Validate phone numbers and email addresses before sending.

**Implementation**:
- Phone number format validation
- Email format validation
- International phone number support (libphonenumber.js)

**Files to Create/Update**:
- `web/src/contact_picker.ts` - Add Contacts API integration
- `web/src/contact_picker_modal.ts` - New: Manual entry modal
- `web/src/media_message_card.ts` - Enhance contact card rendering
- `web/styles/contact_picker_modal.css` - New: Modal styles

---

## Sticker System Enhancements

### Current Implementation

The sticker picker (`web/src/sticker_picker.ts`) is a stub that logs a message. Sticker packs are defined as an empty object.

### Planned Enhancements

#### 1. Sticker Pack Management

**Goal**: Allow users to browse, install, and use sticker packs.

**Implementation Plan**:

1. **Database Schema**
   - Create `StickerPack` model
   - Create `Sticker` model
   - Create `UserStickerPack` model (user's installed packs)

**Migration Example**:

```python
# zerver/migrations/XXXX_add_sticker_system.py

class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "10009_add_rich_media_message_types"),
    ]

    operations = [
        migrations.CreateModel(
            name="StickerPack",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True)),
                ("cover_sticker_id", models.CharField(max_length=100)),
                ("author", models.CharField(max_length=100)),
                ("is_official", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="Sticker",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("sticker_id", models.CharField(max_length=100)),
                ("pack", models.ForeignKey(on_delete=models.CASCADE, to="zerver.stickerpack")),
                ("image", models.ForeignKey(on_delete=models.CASCADE, to="zerver.attachment")),
                ("emoji", models.CharField(max_length=50, blank=True)),  # Associated emoji
                ("keywords", models.JSONField(default=list)),  # Search keywords
            ],
        ),
        migrations.CreateModel(
            name="UserStickerPack",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("user", models.ForeignKey(on_delete=models.CASCADE, to="zerver.userprofile")),
                ("pack", models.ForeignKey(on_delete=models.CASCADE, to="zerver.stickerpack")),
                ("installed_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "unique_together": {("user", "pack")},
            },
        ),
    ]
```

2. **Backend API Endpoints**

**New Endpoints**:
- `GET /api/v1/sticker_packs` - List available sticker packs
- `POST /api/v1/sticker_packs/{pack_id}/install` - Install a pack
- `DELETE /api/v1/sticker_packs/{pack_id}/uninstall` - Uninstall a pack
- `GET /api/v1/sticker_packs/{pack_id}/stickers` - Get stickers in a pack

**Example Implementation**:

```python
# zerver/views/sticker_packs.py

from zerver.decorator import authenticated_json_view
from zerver.models import StickerPack, UserStickerPack, Sticker
from zerver.lib.response import json_success

@authenticated_json_view
def list_sticker_packs(request: HttpRequest, user: UserProfile) -> HttpResponse:
    packs = StickerPack.objects.filter(is_official=True)
    installed_pack_ids = set(
        UserStickerPack.objects.filter(user=user).values_list("pack_id", flat=True)
    )
    
    return json_success({
        "packs": [
            {
                "id": pack.id,
                "name": pack.name,
                "description": pack.description,
                "cover_sticker_id": pack.cover_sticker_id,
                "author": pack.author,
                "is_installed": pack.id in installed_pack_ids,
                "sticker_count": pack.sticker_set.count(),
            }
            for pack in packs
        ]
    })

@authenticated_json_view
def install_sticker_pack(
    request: HttpRequest, user: UserProfile, pack_id: int
) -> HttpResponse:
    pack = StickerPack.objects.get(id=pack_id)
    UserStickerPack.objects.get_or_create(user=user, pack=pack)
    return json_success()
```

3. **Frontend Sticker Picker UI**

**Components**:
- Sticker picker modal with pack browser
- Sticker grid view
- Pack installation UI
- Recent stickers quick-access

**Example Implementation**:

```typescript
// web/src/sticker_picker.ts (enhanced)

interface StickerPack {
    id: number;
    name: string;
    description: string;
    cover_sticker_id: string;
    is_installed: boolean;
    sticker_count: number;
}

interface Sticker {
    sticker_id: string;
    image_url: string;
    emoji?: string;
}

let installed_packs: StickerPack[] = [];
let current_pack_stickers: Sticker[] = [];

export async function initialize(): Promise<void> {
    $(document).on("click", "[data-action='send-sticker']", (event) => {
        event.preventDefault();
        void show_sticker_picker();
    });

    // Load installed packs on page load
    await load_installed_packs();
}

async function load_installed_packs(): Promise<void> {
    const response = await fetch("/api/v1/sticker_packs?installed=true");
    const data = await response.json();
    installed_packs = data.packs.filter((pack: StickerPack) => pack.is_installed);
}

async function show_sticker_picker(): Promise<void> {
    const modal = modals.create_modal({
        title: "Stickers",
        body: render_sticker_picker_body(),
        on_shown: () => {
            load_sticker_packs();
        },
    });

    // Pack selection
    $(document).on("click", ".sticker-pack-item", async function () {
        const pack_id = $(this).data("pack-id");
        await load_pack_stickers(pack_id);
    });

    // Sticker selection
    $(document).on("click", ".sticker-item", function () {
        const sticker_id = $(this).data("sticker-id");
        const pack_id = $(this).data("pack-id");
        send_sticker_message(pack_id, sticker_id);
        modals.close_modal(modal);
    });
}

function render_sticker_picker_body(): string {
    return `
        <div class="sticker-picker-container">
            <div class="sticker-packs-sidebar">
                <div class="sticker-pack-list">
                    ${installed_packs.map(pack => `
                        <div class="sticker-pack-item" data-pack-id="${pack.id}">
                            <img src="/api/v1/stickers/${pack.cover_sticker_id}/image" 
                                 alt="${pack.name}" />
                            <span>${pack.name}</span>
                        </div>
                    `).join("")}
                </div>
                <button class="sticker-pack-browse">Browse Packs</button>
            </div>
            <div class="sticker-grid">
                <!-- Stickers will be loaded here -->
            </div>
        </div>
    `;
}

async function load_pack_stickers(pack_id: number): Promise<void> {
    const response = await fetch(`/api/v1/sticker_packs/${pack_id}/stickers`);
    const data = await response.json();
    current_pack_stickers = data.stickers;
    
    $(".sticker-grid").html(
        current_pack_stickers.map(sticker => `
            <div class="sticker-item" 
                 data-sticker-id="${sticker.sticker_id}"
                 data-pack-id="${pack_id}">
                <img src="${sticker.image_url}" alt="${sticker.emoji || ""}" />
            </div>
        `).join("")
    );
}

function send_sticker_message(pack_id: number, sticker_id: string): void {
    const sticker = current_pack_stickers.find(s => s.sticker_id === sticker_id);
    if (!sticker) return;

    const message_content = compose_state.message_content();
    const message_obj = compose.create_message_object(message_content);
    message_obj.media_type = "sticker";
    message_obj.media_metadata = {
        pack_id: pack_id.toString(),
        sticker_id,
    };
    message_obj.content = "";
    message_obj.primary_attachment_path_id = sticker.image_url;

    compose.send_message(message_obj);
    compose_ui.clear_compose_box();
}
```

#### 2. Sticker Pack Creation Tools

**Goal**: Allow administrators to create and manage sticker packs.

**Implementation**:
- Admin UI for uploading sticker images
- Bulk upload support
- Sticker metadata editor (emoji, keywords)
- Pack preview generator

#### 3. Sticker Search

**Goal**: Allow users to search stickers by emoji or keywords.

**Implementation**:
- Search API endpoint
- Frontend search UI
- Emoji-based filtering
- Keyword matching

#### 4. Animated Stickers

**Goal**: Support animated (GIF/WebP) stickers.

**Implementation**:
- Detect animated images during upload
- Store animation metadata
- Frontend rendering with animation support
- Play/pause controls

#### 5. Sticker Reactions

**Goal**: Allow using stickers as reactions (alternative to emoji reactions).

**Implementation**:
- Extend reaction system to support sticker IDs
- Sticker picker in reaction menu
- Display stickers in reaction list

**Files to Create/Update**:
- `zerver/models/stickers.py` - New: Sticker models
- `zerver/migrations/XXXX_add_sticker_system.py` - New: Migration
- `zerver/views/sticker_packs.py` - New: API endpoints
- `web/src/sticker_picker.ts` - Complete implementation
- `web/src/sticker_picker_modal.ts` - New: Picker UI
- `web/styles/sticker_picker.css` - New: Styles
- `web/src/media_message_card.ts` - Enhance sticker rendering

---

## Implementation Priority

### High Priority
1. **Map UI for Location Picker** - Significantly improves UX for location sharing
2. **Enhanced Contact Picker** - Contacts API integration provides native feel

### Medium Priority
3. **Sticker Pack Management** - Core functionality for sticker system
4. **Contact Card UI Enhancement** - Better display and interaction

### Low Priority
5. **Sticker Search** - Nice-to-have feature
6. **Animated Stickers** - Enhancement for existing system
7. **Sticker Reactions** - Alternative reaction system

## Testing Requirements

For each enhancement, create:

1. **Backend Tests**: `zerver/tests/test_*.py`
   - API endpoint tests
   - Model validation tests
   - Permission/security tests

2. **Frontend Tests**: `web/tests/*.test.cjs`
   - UI component tests
   - User interaction tests
   - Integration tests

3. **E2E Tests**: `web/e2e-tests/*.test.ts`
   - Full user workflows
   - Cross-browser compatibility

## Dependencies

### Map UI
- Leaflet.js or Mapbox GL JS
- Geocoding service (Nominatim, Mapbox, Google Maps API)

### Contact Picker
- Contact Picker API (browser support)
- Phone number validation library (libphonenumber.js)

### Sticker System
- Image processing (Pillow/PIL for thumbnails)
- Admin UI components

## Notes

- All enhancements should maintain backward compatibility
- Consider mobile app implications for each feature
- Document API changes in OpenAPI spec
- Update user-facing help documentation
- Consider privacy implications (especially for Contacts API and Location sharing)
