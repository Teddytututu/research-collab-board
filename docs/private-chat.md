# Private conversations

The discussion header has separate **私聊 GPT** and **私聊 Claude** buttons. Each conversation retains its text and pending-image draft while switching between peers or returning to the public discussion. Drafts stay in the current page; reloading clears them. Enter sends, Shift+Enter inserts a line break, and input-method composition completes before sending.

Select, paste or drop PNG, JPEG, WebP or GIF images into the composer. Each message supports six images, each up to 8 MiB and 16 million pixels. The server decodes and normalizes images to PNG. Preview thumbnails support removal before sending; received images open in a full-screen keyboard-accessible viewer. Escape closes the viewer and restores focus.

## Assistant access

Use the existing project environment and data directory:

```sh
python scripts/private_chat.py --actor GPT --peer GPT
python scripts/private_chat.py --actor GPT --peer GPT --body "I have reviewed your note."
python scripts/private_chat.py --actor Claude --peer Claude
python scripts/private_chat.py --actor Claude --peer Claude --body "Here is my review."
```

`--data-dir` selects the same project data directory used by the board. `--before MESSAGE_ID` reads an earlier page. `--client-id` supplies a stable identifier for a retry with identical content. Assistant tools can call `board.private_notes.history`, `publish` and `image` with their own role and peer; a cross-peer role raises `PermissionError`.

## Local trust and storage

The existing loopback listener treats its browser as `owner`. Browser requests always use that identity; assistant-named identity headers are rejected, and payload fields cannot select an author. The CLI is a trusted local-file interface, like the public discussion posting scripts. The operating-system user who owns these files controls access to the entire project. The role checks provide separation within cooperating assistant workflows rather than independent operating-system accounts.

Private ledgers and images live under `data/attachments/private/`, separately from public discussion and its attachments. Public board snapshots, conversations, collection and unread counts read only public ledgers. Private images require a matching peer and an existing message reference. Public image, file and report routes exclude private storage, even when a report link names it. Source release archives include code and tests through the source allowlist; runtime data stays outside the package.
