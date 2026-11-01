# Kenning Reach on your own computer

Kenning Reach keeps a map of your own experience: what you are working toward, what you decided to let go, what became real, and what you learned along the way. It lives on your computer. Nobody else can see it unless you show them.

You need three things. Each is a normal download.

1. **Docker Desktop** — runs the database and the Reach server in the background. Get it from docker.com and open it once so it finishes setting up.
2. **Claude Desktop** — the assistant you talk to. It writes to your map for you, in your words, and reads it back.
3. **This folder** — the compose file that tells Docker what to run.

## Start it

1. Open the `deploy` folder. Make a copy of `.env.example` and name the copy `.env`. Open `.env` in any text editor and replace `change-me-before-first-start` with a password of your own. Save it.
2. Open Docker Desktop. At the bottom of its window there is a **Terminal** button. Click it.
3. In that terminal, type the two lines below, pressing Enter after each. The first line moves into this folder (drag the folder onto the terminal window if you would rather not type the path).

```
cd path/to/kenning-reach/deploy
docker compose up -d
```

4. The first start downloads a few hundred megabytes and takes a couple of minutes. When Docker Desktop shows two green containers, `reach-neo4j` and `reach`, it is running. It will start again by itself whenever Docker Desktop is open.

## Connect Claude, on the computer and on your phone

Open Claude Desktop and click **Code** in the sidebar. Open this `deploy` folder as the project. The first time, Claude asks whether to trust the folder and whether to use the `reach` server it found in it. Say yes to both. Then, in Claude Desktop's settings under **Claude Code**, turn on **Enable remote control by default**.

That is the whole setup. From now on, every Code session you start here can be picked up on your phone: open the Claude app, tap **Code**, and your session is there with a green dot. Talk to it. Dictate. Whatever you say goes to the Reach on your computer, not to a server somewhere else; the phone is a window into the session running at home.

Ask, on either device: *"Start today. What am I reaching toward?"* The first time, the answer is that nothing is open yet, and that is right. Then say what you are working toward, and Claude will open it for you.

Three things to know:

- The computer has to be on with Claude Desktop running for the phone to reach it. Sleep is fine; it reconnects when the computer wakes. A reboot means opening Claude Desktop again.
- Remote Control needs a Claude Pro or Max subscription. While your phone is connected, the conversation itself passes through Anthropic's servers to reach your computer, the same as any conversation with Claude. Your map does not; it stays in the volume on your machine.
- Do not add Reach as a "custom connector" in Claude's settings. Those are reached from Anthropic's servers and refuse an address on your own machine; the Code session above is the way in.

## Where your map lives

In Docker Desktop, under **Volumes**, there is one named `reach-data`. That is your map. If you delete that volume, the map is gone. If you keep it, everything stays, through restarts and updates.

## Stop it

In the same terminal:

```
docker compose down
```

Your map is kept. To start again, `docker compose up -d`.

## If a port is taken

If Docker complains that a port is already in use, add a line to `.env` such as `REACH_PORT=18000` and start again. Then change `8000` to `18000` in `.mcp.json` in this folder.
