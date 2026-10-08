#![forbid(unsafe_code)]

use eframe::egui;
use reqwest::blocking::Client;
use serde::{Deserialize, Serialize};
use std::sync::mpsc::{self, Receiver, Sender};
use std::thread;
use std::time::Duration;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum View {
    Overview,
    Agents,
    Messages,
    Activity,
    Artifacts,
}

#[derive(Debug, Clone)]
enum Event {
    Started(String),
    Status(TeamSnapshot),
    Audit(AuditStatus),
    Workflows(Vec<Workflow>),
    Artifacts(Vec<Artifact>),
    Error(String),
}

#[derive(Debug, Clone, Deserialize, Default)]
struct Workflow {
    #[serde(default)]
    id: String,
    #[serde(default)]
    name: String,
    #[serde(default)]
    description: String,
    #[serde(default)]
    mode: String,
    #[serde(default)]
    default_agents: u32,
}

#[derive(Debug, Clone, Deserialize, Default)]
struct Agent {
    #[serde(default)]
    agent_id: String,
    #[serde(default)]
    name: String,
    #[serde(default)]
    profession: String,
    #[serde(default)]
    state: String,
    #[serde(default)]
    mission: String,
    #[serde(default)]
    model_role: String,
    #[serde(default)]
    result: Option<String>,
    #[serde(default)]
    error: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
struct Message {
    #[serde(default)]
    sender_id: String,
    #[serde(default)]
    recipient_id: Option<String>,
    #[serde(default)]
    message_type: String,
    #[serde(default)]
    payload: serde_json::Value,
}

#[derive(Debug, Clone, Deserialize, Default)]
struct ActivityEvent {
    #[serde(default)]
    event_type: String,
    #[serde(default)]
    agent_id: Option<String>,
    #[serde(default)]
    payload: serde_json::Value,
}

#[derive(Debug, Clone, Deserialize, Default)]
struct Artifact {
    #[serde(default)]
    name: String,
    #[serde(default)]
    size: u64,
}

#[derive(Debug, Clone, Deserialize, Default)]
struct TeamResult {
    #[serde(default)]
    synthesis: String,
    #[serde(default)]
    artifact_paths: Vec<String>,
    #[serde(default)]
    summary: String,
    #[serde(default)]
    quality: serde_json::Value,
}

#[derive(Debug, Clone, Deserialize, Default)]
struct TeamSnapshot {
    #[serde(default)]
    status: String,
    #[serde(default)]
    team_id: Option<String>,
    #[serde(default)]
    agents: Vec<Agent>,
    #[serde(default)]
    messages: Vec<Message>,
    #[serde(default)]
    events: Vec<ActivityEvent>,
    #[serde(default)]
    result: Option<TeamResult>,
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

#[derive(Debug, Serialize)]
#[serde(tag = "action", rename_all = "lowercase")]
enum ControlAction {
    Pause,
    Resume,
    Stop,
}

enum Command {
    Start {
        endpoint: String,
        goal: String,
        workflow: String,
        mode: String,
        effort: String,
        depth: String,
        collection: String,
        source_strategy: String,
        max_minutes: u32,
        idle_rounds: u32,
        sources: Vec<String>,
        agents: Vec<String>,
        max_agents: u32,
        parallelism: u32,
        output_mode: String,
        output_format: String,
    },
    Control {
        endpoint: String,
        team_id: String,
        action: ControlAction,
    },
    Refresh {
        endpoint: String,
        job_id: String,
    },
    LoadWorkflows {
        endpoint: String,
    },
    LoadArtifacts {
        endpoint: String,
        team_id: String,
    },
    VerifyAudit {
        endpoint: String,
    },
}

struct NexusDesktop {
    endpoint: String,
    goal: String,
    workflow: String,
    workflows: Vec<Workflow>,
    mode: String,
    effort: String,
    depth: String,
    collection: String,
    source_strategy: String,
    max_minutes: u32,
    idle_rounds: u32,
    sources: String,
    pinned_agents: String,
    max_agents: u32,
    parallelism: u32,
    output_mode: String,
    output_format: String,
    job_id: String,
    team_id: String,
    status: String,
    agents: Vec<Agent>,
    messages: Vec<Message>,
    events: Vec<ActivityEvent>,
    artifacts: Vec<Artifact>,
    synthesis: String,
    audit: AuditStatus,
    errors: Vec<String>,
    view: View,
    commands: Sender<Command>,
    events_rx: Receiver<Event>,
}

impl NexusDesktop {
    fn new() -> Self {
        let (command_tx, command_rx) = mpsc::channel::<Command>();
        let (event_tx, event_rx) = mpsc::channel::<Event>();
        thread::spawn(move || worker_loop(command_rx, event_tx));

        let _ = command_tx.send(Command::LoadWorkflows {
            endpoint: "http://127.0.0.1:7860".into(),
        });

        Self {
            endpoint: "http://127.0.0.1:7860".into(),
            goal: String::new(),
            workflow: String::new(),
            workflows: Vec::new(),
            mode: "auto".into(),
            effort: "medium".into(),
            depth: "detailed".into(),
            collection: "until_saturation".into(),
            source_strategy: "hybrid".into(),
            max_minutes: 10080,
            idle_rounds: 2,
            sources: String::new(),
            pinned_agents: String::new(),
            max_agents: 6,
            parallelism: 4,
            output_mode: "chat".into(),
            output_format: "markdown".into(),
            job_id: String::new(),
            team_id: String::new(),
            status: "idle".into(),
            agents: Vec::new(),
            messages: Vec::new(),
            events: Vec::new(),
            artifacts: Vec::new(),
            synthesis: String::new(),
            audit: AuditStatus::default(),
            errors: Vec::new(),
            view: View::Overview,
            commands: command_tx,
            events_rx: event_rx,
        }
    }

    fn poll_events(&mut self) {
        while let Ok(event) = self.events_rx.try_recv() {
            match event {
                Event::Started(job_id) => {
                    self.job_id = job_id;
                    self.status = "queued".into();
                }
                Event::Status(snapshot) => {
                    self.status = snapshot.status.clone();
                    self.team_id = snapshot.team_id.unwrap_or_default();
                    self.agents = snapshot.agents;
                    self.messages = snapshot.messages;
                    self.events = snapshot.events;
                    if let Some(result) = snapshot.result {
                        self.synthesis = if result.synthesis.is_empty() {
                            result.summary
                        } else {
                            result.synthesis
                        };
                    }
                }
                Event::Audit(value) => self.audit = value,
                Event::Workflows(items) => self.workflows = items,
                Event::Artifacts(items) => self.artifacts = items,
                Event::Error(error) => self.errors.push(error),
            }
        }
    }

    fn send_control(&mut self, action: ControlAction) {
        if self.team_id.is_empty() {
            return;
        }
        let _ = self.commands.send(Command::Control {
            endpoint: self.endpoint.clone(),
            team_id: self.team_id.clone(),
            action,
        });
    }
}

impl eframe::App for NexusDesktop {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.poll_events();

        egui::TopBottomPanel::top("top").show(ctx, |ui| {
            ui.horizontal_wrapped(|ui| {
                ui.heading("NexusAgent");
                ui.label("Native Multi-Agent Command Center");
                ui.separator();
                ui.label(format!("{} • {}", self.status, if self.team_id.is_empty() { "no-team" } else { &self.team_id }));
                if self.audit.valid {
                    ui.colored_label(egui::Color32::from_rgb(134, 239, 172), "AUDIT VALID");
                }
            });
        });

        egui::SidePanel::left("control").resizable(true).show(ctx, |ui| {
            ui.heading("Task Control");
            ui.label("Local server");
            ui.text_edit_singleline(&mut self.endpoint);

            ui.label("Goal");
            ui.add(
                egui::TextEdit::multiline(&mut self.goal)
                    .desired_rows(7)
                    .desired_width(f32::INFINITY),
            );

            ui.horizontal(|ui| {
                egui::ComboBox::from_label("Workflow")
                    .selected_text(if self.workflow.is_empty() { "Ad hoc" } else { self.workflow.as_str() })
                    .show_ui(ui, |ui| {
                        ui.selectable_value(&mut self.workflow, String::new(), "Ad hoc");
                        for workflow in &self.workflows {
                            ui.selectable_value(
                                &mut self.workflow,
                                workflow.id.clone(),
                                workflow.name.clone(),
                            );
                        }
                    });
            });

            egui::ComboBox::from_label("Mode")
                .selected_text(&self.mode)
                .show_ui(ui, |ui| {
                    for mode in ["auto", "code", "research", "review", "analysis", "plan", "automation"] {
                        ui.selectable_value(&mut self.mode, mode.to_string(), mode);
                    }
                });

            egui::ComboBox::from_label("Research depth")
                .selected_text(&self.depth)
                .show_ui(ui, |ui| {
                    for depth in [
                        "glance", "surface", "shallow", "basic", "preliminary",
                        "exploratory", "focused", "detailed", "deep", "very_deep",
                        "comprehensive", "exhaustive", "atomic", "molecular",
                        "cellular", "planetary", "stellar", "galactic", "cosmic",
                        "universal", "maximal",
                    ] {
                        ui.selectable_value(&mut self.depth, depth.to_string(), depth);
                    }
                });

            egui::ComboBox::from_label("Collection")
                .selected_text(&self.collection)
                .show_ui(ui, |ui| {
                    for value in ["bounded", "until_saturation", "continuous"] {
                        ui.selectable_value(&mut self.collection, value.to_string(), value);
                    }
                });

            egui::ComboBox::from_label("Source strategy")
                .selected_text(&self.source_strategy)
                .show_ui(ui, |ui| {
                    for value in ["user_only", "hybrid", "autonomous"] {
                        ui.selectable_value(&mut self.source_strategy, value.to_string(), value);
                    }
                });

            ui.add(egui::Slider::new(&mut self.max_agents, 1..=64).text("max agents"));
            ui.add(egui::Slider::new(&mut self.parallelism, 1..=32).text("parallelism"));
            ui.add(egui::Slider::new(&mut self.max_minutes, 1..=525600).text("max research minutes"));
            ui.add(egui::Slider::new(&mut self.idle_rounds, 1..=20).text("idle rounds"));

            ui.label("Seed sources (one URL per line)");
            ui.add(egui::TextEdit::multiline(&mut self.sources).desired_rows(3));

            ui.label("Pinned agent IDs (comma separated)");
            ui.text_edit_singleline(&mut self.pinned_agents);

            ui.horizontal(|ui| {
                if ui.button("Start Team").clicked() {
                    if self.goal.trim().is_empty() {
                        self.errors.push("Enter a goal first.".into());
                    } else {
                        let _ = self.commands.send(Command::Start {
                            endpoint: self.endpoint.clone(),
                            goal: self.goal.clone(),
                            workflow: self.workflow.clone(),
                            mode: self.mode.clone(),
                            effort: self.effort.clone(),
                            depth: self.depth.clone(),
                            collection: self.collection.clone(),
                            source_strategy: self.source_strategy.clone(),
                            max_minutes: self.max_minutes,
                            idle_rounds: self.idle_rounds,
                            sources: self.sources.lines().map(|s| s.trim()).filter(|s| !s.is_empty()).map(str::to_string).collect(),
                            agents: self.pinned_agents.split(',').map(|s| s.trim()).filter(|s| !s.is_empty()).map(str::to_string).collect(),
                            max_agents: self.max_agents,
                            parallelism: self.parallelism,
                            output_mode: self.output_mode.clone(),
                            output_format: self.output_format.clone(),
                        });
                        self.status = "starting".into();
                    }
                }
                if ui.button("Pause").clicked() {
                    self.send_control(ControlAction::Pause);
                }
                if ui.button("Resume").clicked() {
                    self.send_control(ControlAction::Resume);
                }
                if ui.button("Stop").clicked() {
                    self.send_control(ControlAction::Stop);
                }
            });

            ui.horizontal(|ui| {
                if ui.button("Refresh").clicked() && !self.job_id.is_empty() {
                    let _ = self.commands.send(Command::Refresh {
                        endpoint: self.endpoint.clone(),
                        job_id: self.job_id.clone(),
                    });
                }
                if ui.button("Verify Audit").clicked() {
                    let _ = self.commands.send(Command::VerifyAudit {
                        endpoint: self.endpoint.clone(),
                    });
                }
            });

            if !self.errors.is_empty() {
                ui.separator();
                ui.colored_label(egui::Color32::from_rgb(250, 165, 165), "Errors");
                egui::ScrollArea::vertical().max_height(160.0).show(ui, |ui| {
                    for error in self.errors.iter().rev().take(8) {
                        ui.label(error);
                    }
                });
            }
        });

        egui::TopBottomPanel::bottom("tabs").show(ctx, |ui| {
            ui.horizontal(|ui| {
                for (view, label) in [
                    (View::Overview, "Overview"),
                    (View::Agents, "Agents"),
                    (View::Messages, "Messages"),
                    (View::Activity, "Activity"),
                    (View::Artifacts, "Artifacts"),
                ] {
                    ui.selectable_value(&mut self.view, view, label);
                }
            });
        });

        egui::CentralPanel::default().show(ctx, |ui| {
            match self.view {
                View::Overview => {
                    ui.heading("Team Overview");
                    ui.label(format!("Job: {}", if self.job_id.is_empty() { "—" } else { &self.job_id }));
                    ui.label(format!("Agents: {} • Messages: {} • Events: {} • Artifacts: {}", self.agents.len(), self.messages.len(), self.events.len(), self.artifacts.len()));
                    ui.separator();
                    ui.heading("Integrated Result");
                    egui::ScrollArea::vertical().show(ui, |ui| {
                        ui.label(if self.synthesis.is_empty() {
                            "Awaiting team completion.".to_string()
                        } else {
                            self.synthesis.clone()
                        });
                    });
                    ui.separator();
                    ui.heading("Audit Integrity");
                    ui.horizontal_wrapped(|ui| {
                        ui.label(if self.audit.valid { "CHAIN VALID" } else { "CHAIN UNVERIFIED" });
                        ui.label(format!("records: {}", self.audit.records));
                        if !self.audit.last_hash.is_empty() {
                            ui.label(format!("hash: {}…", &self.audit.last_hash[..self.audit.last_hash.len().min(20)]));
                        }
                    });
                }
                View::Agents => {
                    ui.heading("Agent Topology");
                    egui::ScrollArea::vertical().show(ui, |ui| {
                        for agent in &self.agents {
                            ui.group(|ui| {
                                ui.horizontal(|ui| {
                                    ui.strong(&agent.name);
                                    ui.separator();
                                    ui.label(&agent.profession);
                                    ui.separator();
                                    ui.label(&agent.state);
                                });
                                ui.label(format!("role: {} • {}", agent.agent_id, agent.model_role));
                                ui.label(&agent.mission);
                                if let Some(error) = &agent.error {
                                    ui.colored_label(egui::Color32::from_rgb(250, 165, 165), error);
                                }
                            });
                        }
                    });
                }
                View::Messages => {
                    ui.heading("Peer Communication");
                    egui::ScrollArea::vertical().show(ui, |ui| {
                        for message in self.messages.iter().rev() {
                            let body = message.payload.get("message").and_then(|x| x.as_str()).unwrap_or_else(|| message.payload.to_string().as_str()).to_string();
                            ui.group(|ui| {
                                ui.label(format!(
                                    "{} → {} • {}",
                                    message.sender_id,
                                    message.recipient_id.as_deref().unwrap_or("TEAM"),
                                    message.message_type
                                ));
                                ui.label(body);
                            });
                        }
                    });
                }
                View::Activity => {
                    ui.heading("Execution Activity");
                    egui::ScrollArea::vertical().show(ui, |ui| {
                        for event in self.events.iter().rev() {
                            ui.group(|ui| {
                                ui.label(format!(
                                    "{}{}",
                                    event.event_type,
                                    event.agent_id.as_deref().map(|id| format!(" • {id}")).unwrap_or_default()
                                ));
                                ui.label(event.payload.to_string());
                            });
                        }
                    });
                }
                View::Artifacts => {
                    ui.heading("Artifacts");
                    egui::ScrollArea::vertical().show(ui, |ui| {
                        for artifact in &self.artifacts {
                            ui.group(|ui| {
                                ui.label(&artifact.name);
                                ui.label(format!("{} bytes", artifact.size));
                            });
                        }
                    });
                }
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
            Command::Start {
                endpoint,
                goal,
                workflow,
                mode,
                effort,
                depth,
                collection,
                source_strategy,
                max_minutes,
                idle_rounds,
                sources,
                agents,
                max_agents,
                parallelism,
                output_mode,
                output_format,
            } => {
                let result = client
                    .post(format!("{}/api/teams", endpoint.trim_end_matches('/')))
                    .json(&serde_json::json!({
                        "goal": goal,
                        "workflow_id": if workflow.is_empty() { serde_json::Value::Null } else { serde_json::Value::String(workflow) },
                        "mode": mode,
                        "max_agents": max_agents,
                        "parallelism": parallelism,
                        "max_iterations_per_agent": 30,
                        "effort_level": effort,
                        "output_mode": output_mode,
                        "output_format": output_format,
                        "research_depth": depth,
                        "research_collection": collection,
                        "research_source_strategy": source_strategy,
                        "research_max_minutes": max_minutes,
                        "research_idle_rounds": idle_rounds,
                        "research_source_urls": sources,
                        "agent_ids": agents,
                        "use_saved_agents": true,
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
            Command::Control { endpoint, team_id, action } => {
                let action_name = match action {
                    ControlAction::Pause => "pause",
                    ControlAction::Resume => "resume",
                    ControlAction::Stop => "stop",
                };
                let result = client
                    .post(format!("{}/api/teams/{}/control", endpoint.trim_end_matches('/'), team_id))
                    .json(&serde_json::json!({ "action": action_name }))
                    .send()
                    .and_then(|response| response.error_for_status());
                if let Err(error) = result {
                    let _ = tx.send(Event::Error(format!("Team control failed: {error}")));
                }
            }
            Command::Refresh { endpoint, job_id } => {
                poll_team(&client, &tx, &endpoint, &job_id);
            }
            Command::LoadWorkflows { endpoint } => {
                match client
                    .get(format!("{}/api/workflows", endpoint.trim_end_matches('/')))
                    .send()
                    .and_then(|response| response.error_for_status())
                    .and_then(|response| response.json::<serde_json::Value>())
                {
                    Ok(value) => {
                        let workflows = serde_json::from_value::<Vec<Workflow>>(
                            value.get("workflows").cloned().unwrap_or_else(|| serde_json::json!([]))
                        ).unwrap_or_default();
                        let _ = tx.send(Event::Workflows(workflows));
                    }
                    Err(error) => {
                        let _ = tx.send(Event::Error(format!("Workflow list failed: {error}")));
                    }
                }
            }
            Command::LoadArtifacts { endpoint, team_id } => {
                match client
                    .get(format!("{}/api/teams/{}/artifacts", endpoint.trim_end_matches('/'), team_id))
                    .send()
                    .and_then(|response| response.error_for_status())
                    .and_then(|response| response.json::<serde_json::Value>())
                {
                    Ok(value) => {
                        let artifacts = serde_json::from_value::<Vec<Artifact>>(
                            value.get("artifacts").cloned().unwrap_or_else(|| serde_json::json!([]))
                        ).unwrap_or_default();
                        let _ = tx.send(Event::Artifacts(artifacts));
                    }
                    Err(error) => {
                        let _ = tx.send(Event::Error(format!("Artifact list failed: {error}")));
                    }
                }
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
            .and_then(|response| response.json::<TeamSnapshot>())
        {
            Ok(status) => {
                let terminal = matches!(status.status.as_str(), "completed" | "needs_review" | "failed" | "cancelled");
                if let Some(team_id) = status.team_id.clone() {
                    let _ = tx.send(Event::Artifacts(Vec::new()));
                    let _ = client
                        .get(format!("{}/api/teams/{}/artifacts", endpoint.trim_end_matches('/'), team_id))
                        .send()
                        .and_then(|response| response.error_for_status())
                        .and_then(|response| response.json::<serde_json::Value>())
                        .ok()
                        .and_then(|value| serde_json::from_value::<Vec<Artifact>>(value.get("artifacts").cloned().unwrap_or_else(|| serde_json::json!([]))).ok())
                        .map(|artifacts| tx.send(Event::Artifacts(artifacts)));
                }
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
