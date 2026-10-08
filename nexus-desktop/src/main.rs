#![forbid(unsafe_code)]

use eframe::egui;
use reqwest::blocking::Client;
use serde::Deserialize;
use std::sync::mpsc::{self, Receiver, Sender};
use std::thread;
use std::time::Duration;

#[derive(Debug, Clone)]
enum Event {
    Started(String),
    Status(TeamStatus),
    Audit(AuditStatus),
    Error(String),
}

#[derive(Debug, Clone, Deserialize, Default)]
struct TeamStatus {
    #[serde(default)]
    status: String,
    #[serde(default)]
    team_id: Option<String>,
    #[serde(default)]
    agents: Vec<Agent>,
}

#[derive(Debug, Clone, Deserialize, Default)]
struct Agent {
    #[serde(default)]
    name: String,
    #[serde(default)]
    profession: String,
    #[serde(default)]
    state: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
struct AuditStatus {
    #[serde(default)]
    valid: bool,
    #[serde(default)]
    records: usize,
    #[serde(default)]
    last_hash: String,
}

enum Command {
    Start {
        endpoint: String,
        goal: String,
        mode: String,
        max_agents: u32,
        parallelism: u32,
    },
    Refresh {
        endpoint: String,
        job_id: String,
    },
    VerifyAudit {
        endpoint: String,
    },
}

struct NexusDesktop {
    endpoint: String,
    goal: String,
    mode: String,
    max_agents: u32,
    parallelism: u32,
    job_id: String,
    status: String,
    team_id: String,
    agents: Vec<Agent>,
    audit: AuditStatus,
    errors: Vec<String>,
    commands: Sender<Command>,
    events: Receiver<Event>,
}

impl NexusDesktop {
    fn new() -> Self {
        let (command_tx, command_rx) = mpsc::channel::<Command>();
        let (event_tx, event_rx) = mpsc::channel::<Event>();

        thread::spawn(move || worker_loop(command_rx, event_tx));

        Self {
            endpoint: "http://127.0.0.1:7860".into(),
            goal: String::new(),
            mode: "auto".into(),
            max_agents: 6,
            parallelism: 4,
            job_id: String::new(),
            status: "idle".into(),
            team_id: String::new(),
            agents: Vec::new(),
            audit: AuditStatus::default(),
            errors: Vec::new(),
            commands: command_tx,
            events: event_rx,
        }
    }

    fn poll_events(&mut self) {
        while let Ok(event) = self.events.try_recv() {
            match event {
                Event::Started(job) => {
                    self.job_id = job;
                    self.status = "queued".into();
                }
                Event::Status(value) => {
                    self.status = value.status.clone();
                    self.team_id = value.team_id.unwrap_or_default();
                    self.agents = value.agents;
                }
                Event::Audit(value) => self.audit = value,
                Event::Error(error) => self.errors.push(error),
            }
        }
    }
}

impl eframe::App for NexusDesktop {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.poll_events();

        egui::TopBottomPanel::top("top").show(ctx, |ui| {
            ui.horizontal(|ui| {
                ui.heading("NexusAgent");
                ui.label("Native Multi-Agent Workbench");
                ui.separator();
                ui.label(format!("status: {}", self.status));
                if !self.team_id.is_empty() {
                    ui.label(format!("team: {}", self.team_id));
                }
            });
        });

        egui::SidePanel::left("control").show(ctx, |ui| {
            ui.heading("Task Control");
            ui.label("Local server endpoint");
            ui.text_edit_singleline(&mut self.endpoint);

            ui.label("Goal");
            ui.add(
                egui::TextEdit::multiline(&mut self.goal)
                    .desired_rows(8)
                    .desired_width(260.0),
            );

            egui::ComboBox::from_label("Mode")
                .selected_text(&self.mode)
                .show_ui(ui, |ui| {
                    for mode in ["auto", "code", "research", "review", "analysis", "plan", "automation"] {
                        ui.selectable_value(&mut self.mode, mode.to_string(), mode);
                    }
                });

            ui.add(egui::Slider::new(&mut self.max_agents, 1..=64).text("max agents"));
            ui.add(egui::Slider::new(&mut self.parallelism, 1..=32).text("parallelism"));

            if ui.button("Assemble Team & Start").clicked() {
                if self.goal.trim().is_empty() {
                    self.errors.push("Enter a goal first.".into());
                } else {
                    let _ = self.commands.send(Command::Start {
                        endpoint: self.endpoint.clone(),
                        goal: self.goal.clone(),
                        mode: self.mode.clone(),
                        max_agents: self.max_agents,
                        parallelism: self.parallelism,
                    });
                    self.status = "starting".into();
                }
            }

            if ui.button("Verify Audit Chain").clicked() {
                let _ = self.commands.send(Command::VerifyAudit {
                    endpoint: self.endpoint.clone(),
                });
            }

            if !self.errors.is_empty() {
                ui.separator();
                ui.colored_label(egui::Color32::from_rgb(250, 165, 165), "Errors");
                for error in self.errors.iter().rev().take(6) {
                    ui.label(error);
                }
            }
        });

        egui::CentralPanel::default().show(ctx, |ui| {
            ui.heading("Team Topology");
            ui.label(format!("Job: {}", if self.job_id.is_empty() { "—" } else { &self.job_id }));

            for agent in &self.agents {
                ui.group(|ui| {
                    ui.horizontal(|ui| {
                        ui.strong(&agent.name);
                        ui.separator();
                        ui.label(&agent.profession);
                        ui.separator();
                        ui.label(&agent.state);
                    });
                });
            }

            ui.separator();
            ui.heading("Audit Integrity");
            ui.horizontal(|ui| {
                ui.label(if self.audit.valid { "CHAIN VALID" } else { "CHAIN INVALID" });
                ui.label(format!("records: {}", self.audit.records));
                if !self.audit.last_hash.is_empty() {
                    ui.label(format!("hash: {}…", &self.audit.last_hash[..self.audit.last_hash.len().min(20)]));
                }
            });

            if self.job_id.is_empty() {
                ui.separator();
                ui.label("Start a team from the left panel. The native client uses the same local server and orchestration runtime as the web console.");
            }
        });

        ctx.request_repaint_after(Duration::from_millis(500));
    }
}

fn worker_loop(rx: Receiver<Command>, tx: Sender<Event>) {
    let client = match Client::builder().timeout(Duration::from_secs(120)).build() {
        Ok(value) => value,
        Err(error) => {
            let _ = tx.send(Event::Error(format!("HTTP client initialization failed: {error}")));
            return;
        }
    };

    while let Ok(command) = rx.recv() {
        match command {
            Command::Start { endpoint, goal, mode, max_agents, parallelism } => {
                let result = client
                    .post(format!("{}/api/teams", endpoint.trim_end_matches('/')))
                    .json(&serde_json::json!({
                        "goal": goal,
                        "mode": mode,
                        "max_agents": max_agents,
                        "parallelism": parallelism,
                        "max_iterations_per_agent": 30,
                        "effort_level": "medium",
                        "output_mode": "chat",
                        "output_format": "markdown",
                        "require_reviewer": true,
                        "auto_synthesize": true,
                        "auto_approve_tools": false
                    }))
                    .send()
                    .and_then(|response| response.error_for_status())
                    .and_then(|response| response.json::<serde_json::Value>())
                    .map_err(|error| error.to_string());

                match result {
                    Ok(value) => {
                        let job_id = value.get("job_id").and_then(|x| x.as_str()).unwrap_or("").to_string();
                        if job_id.is_empty() {
                            let _ = tx.send(Event::Error("Team API returned no job_id.".into()));
                            continue;
                        }
                        let _ = tx.send(Event::Started(job_id.clone()));
                        poll_team(&client, &tx, &endpoint, &job_id);
                    }
                    Err(error) => {
                        let _ = tx.send(Event::Error(error));
                    }
                }
            }
            Command::Refresh { endpoint, job_id } => {
                poll_team(&client, &tx, &endpoint, &job_id);
            }
            Command::VerifyAudit { endpoint } => {
                match client
                    .get(format!("{}/api/audit/verify", endpoint.trim_end_matches('/')))
                    .send()
                    .and_then(|response| response.error_for_status())
                    .and_then(|response| response.json::<AuditStatus>())
                {
                    Ok(value) => {
                        let _ = tx.send(Event::Audit(value));
                    }
                    Err(error) => {
                        let _ = tx.send(Event::Error(format!("Audit verification failed: {error}")));
                    }
                }
            }
        }
    }
}

fn poll_team(client: &Client, tx: &Sender<Event>, endpoint: &str, job_id: &str) {
    for _ in 0..240 {
        match client
            .get(format!("{}/api/teams/{}", endpoint.trim_end_matches('/'), job_id))
            .send()
            .and_then(|response| response.error_for_status())
            .and_then(|response| response.json::<TeamStatus>())
        {
            Ok(status) => {
                let terminal = matches!(status.status.as_str(), "completed" | "needs_review" | "failed" | "cancelled");
                let _ = tx.send(Event::Status(status));
                if terminal {
                    return;
                }
            }
            Err(error) => {
                let _ = tx.send(Event::Error(format!("Team status request failed: {error}")));
                return;
            }
        }
        thread::sleep(Duration::from_secs(1));
    }
    let _ = tx.send(Event::Error("Team polling timed out after 240 seconds.".into()));
}

fn main() -> eframe::Result {
    let options = eframe::NativeOptions::default();
    eframe::run_native(
        "NexusAgent",
        options,
        Box::new(|_creation_context| Ok(Box::new(NexusDesktop::new()))),
    )
}
