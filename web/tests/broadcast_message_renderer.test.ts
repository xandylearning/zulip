/**
 * Tests for broadcast message renderer
 */

import {strict as assert} from "assert";

import type {Message} from "../src/message_store";
import * as broadcast_renderer from "../src/broadcast_message_renderer";

describe("broadcast_message_renderer", () => {
    describe("isBroadcastMessage", () => {
        it("returns true for messages with broadcast_template_data", () => {
            const message = {
                id: 1,
                broadcast_template_data: {
                    template_id: 1,
                    template_structure: {blocks: []},
                    media_content: {},
                    message_type: "broadcast_notification" as const,
                },
            } as Message;

            assert.equal(broadcast_renderer.isBroadcastMessage(message), true);
        });

        it("returns false for messages without broadcast_template_data", () => {
            const message = {
                id: 1,
                broadcast_template_data: null,
            } as Message;

            assert.equal(broadcast_renderer.isBroadcastMessage(message), false);
        });

        it("returns false for messages with undefined broadcast_template_data", () => {
            const message = {
                id: 1,
            } as Message;

            assert.equal(broadcast_renderer.isBroadcastMessage(message), false);
        });
    });

    describe("getBroadcastTemplateData", () => {
        it("returns template data for broadcast messages", () => {
            const templateData = {
                template_id: 1,
                template_structure: {blocks: []},
                media_content: {},
                message_type: "broadcast_notification" as const,
            };

            const message = {
                id: 1,
                broadcast_template_data: templateData,
            } as Message;

            const result = broadcast_renderer.getBroadcastTemplateData(message);
            assert.deepEqual(result, templateData);
        });

        it("returns null for non-broadcast messages", () => {
            const message = {
                id: 1,
                broadcast_template_data: null,
            } as Message;

            const result = broadcast_renderer.getBroadcastTemplateData(message);
            assert.equal(result, null);
        });
    });

    describe("renderBroadcastMessage", () => {
        it("renders text blocks correctly", () => {
            const message = {
                id: 123,
                broadcast_template_data: {
                    template_id: 1,
                    template_structure: {
                        blocks: [
                            {
                                id: "text_1",
                                type: "text" as const,
                                content: "Hello World",
                            },
                        ],
                    },
                    media_content: {
                        text_1: "Custom text content",
                    },
                    message_type: "broadcast_notification" as const,
                },
            } as Message;

            const html = broadcast_renderer.renderBroadcastMessage(message);

            assert.ok(html.includes('class="broadcast-template-message"'));
            assert.ok(html.includes('data-message-id="123"'));
            assert.ok(html.includes('Custom text content'));
        });

        it("renders button blocks correctly", () => {
            const message = {
                id: 456,
                broadcast_template_data: {
                    template_id: 1,
                    template_structure: {
                        blocks: [
                            {
                                id: "button_1",
                                type: "button" as const,
                                text: "Click Me",
                                url: "https://example.com",
                                actionType: "url" as const,
                                style: {
                                    backgroundColor: "#007bff",
                                    textColor: "#ffffff",
                                    borderRadius: 4,
                                    size: "medium" as const,
                                },
                            },
                        ],
                    },
                    media_content: {
                        button_1: "https://example.com",
                    },
                    message_type: "broadcast_notification" as const,
                },
            } as Message;

            const html = broadcast_renderer.renderBroadcastMessage(message);

            assert.ok(html.includes('class="broadcast-button"'));
            assert.ok(html.includes('Click Me'));
            assert.ok(html.includes('data-action-type="url"'));
            assert.ok(html.includes('data-message-id="456"'));
        });

        it("renders image blocks correctly", () => {
            const message = {
                id: 789,
                broadcast_template_data: {
                    template_id: 1,
                    template_structure: {
                        blocks: [
                            {
                                id: "image_1",
                                type: "image" as const,
                                label: "Test Image",
                                alt: "A test image",
                                required: false,
                            },
                        ],
                    },
                    media_content: {
                        image_1: "https://example.com/image.jpg",
                    },
                    message_type: "broadcast_notification" as const,
                },
            } as Message;

            const html = broadcast_renderer.renderBroadcastMessage(message);

            assert.ok(html.includes('class="broadcast-image-block"'));
            assert.ok(html.includes('src="https://example.com/image.jpg"'));
            assert.ok(html.includes('alt="A test image"'));
        });

        it("handles messages without media_content gracefully", () => {
            const message = {
                id: 111,
                broadcast_template_data: {
                    template_id: 1,
                    template_structure: {
                        blocks: [
                            {
                                id: "text_1",
                                type: "text" as const,
                                content: "Default content",
                            },
                        ],
                    },
                    media_content: {},
                    message_type: "broadcast_notification" as const,
                },
            } as Message;

            const html = broadcast_renderer.renderBroadcastMessage(message);

            assert.ok(html.includes('Default content'));
        });

        it("returns original content for non-broadcast messages", () => {
            const message = {
                id: 222,
                content: "Regular message content",
                broadcast_template_data: null,
            } as Message;

            const html = broadcast_renderer.renderBroadcastMessage(message);

            assert.equal(html, "Regular message content");
        });
    });
});
