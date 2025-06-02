/**
 * Kill Network Implementation: D3.js Interactive Force-Directed Graph
 * 
 * This module implements a sophisticated network visualization using D3.js v7
 * for displaying combat relationships in DCS World missions.
 * 
 * Architecture:
 * - Graphics Engine: D3.js v7 with SVG rendering
 * - Physics: Force simulation with collision detection
 * - Interaction: Drag, hover, and click events
 * - Analytics: Real-time network statistics
 */

class KillNetwork {
    constructor(containerId, data) {
        this.containerId = containerId;
        this.data = data;
        this.width = 800;
        this.height = 600;
        this.simulation = null;
        this.svg = null;
        this.nodes = new Map();
        this.links = [];
        
        // Color scheme from configuration
        this.colors = {
            primary: '#4a90e2',    // Blue coalition
            danger: '#e53e3e',     // Red coalition
            ground: '#8B4513',     // Ground targets (brown)
            airToAir: '#e74c3c',   // Air-to-air links (red)
            airToGround: '#27ae60' // Air-to-ground links (green)
        };
        
        this.init();
    }
    
    init() {
        this.processData();
        this.createSVG();
        this.setupSimulation();
        this.render();
        this.setupEventHandlers();
        this.updateAnalytics();
    }
    
    /**
     * Data Processing Pipeline
     * Transforms combat data into graph nodes and links
     */
    processData() {
        if (!this.data || !this.data.air_to_air || !this.data.air_to_ground) {
            console.warn('No combat data available for network visualization');
            return;
        }
        
        // Process Air-to-Air engagements
        this.data.air_to_air.engagements?.forEach((engagement, index) => {
            const killerId = engagement.killer;
            const victimId = engagement.victim;
            
            // Create pilot nodes
            if (!this.nodes.has(killerId)) {
                this.nodes.set(killerId, {
                    id: killerId,
                    type: 'pilot',
                    kills: 0,
                    deaths: 0,
                    coalition: engagement.killer_coalition,
                    aircraft: this.extractAircraft(killerId)
                });
            }
            
            if (!this.nodes.has(victimId)) {
                this.nodes.set(victimId, {
                    id: victimId,
                    type: 'pilot', 
                    kills: 0,
                    deaths: 0,
                    coalition: engagement.victim_coalition,
                    aircraft: this.extractAircraft(victimId)
                });
            }
            
            // Update kill/death counts
            this.nodes.get(killerId).kills++;
            this.nodes.get(victimId).deaths++;
            
            // Create link (directed edge)
            this.links.push({
                source: killerId,
                target: victimId,
                weapon: engagement.weapon,
                time: engagement.time,
                type: 'air_to_air',
                id: `aa_${index}`
            });
        });
        
        // Process Air-to-Ground engagements
        this.data.air_to_ground.ground_kills?.forEach((kill, index) => {
            const pilotId = kill.pilot;
            const targetId = `${kill.target}_${index + 1}`;
            
            // Create pilot node if not exists
            if (!this.nodes.has(pilotId)) {
                this.nodes.set(pilotId, {
                    id: pilotId,
                    type: 'pilot',
                    kills: 0,
                    deaths: 0,
                    coalition: kill.coalition,
                    aircraft: this.extractAircraft(pilotId)
                });
            }
            
            // Create ground target node
            this.nodes.set(targetId, {
                id: targetId,
                type: 'ground_target',
                target_type: kill.target,
                coalition: 0, // Neutral
                destroyed_by: kill.weapon,
                time: kill.time
            });
            
            // Update pilot ground kills
            this.nodes.get(pilotId).kills++;
            
            // Create air-to-ground link
            this.links.push({
                source: pilotId,
                target: targetId,
                weapon: kill.weapon,
                time: kill.time,
                type: 'air_to_ground',
                id: `ag_${index}`
            });
        });
        
        console.log(`Network processed: ${this.nodes.size} nodes, ${this.links.length} links`);
    }
    
    extractAircraft(pilotName) {
        // Extract aircraft type from pilot name (e.g., "F-16C Viper #2" -> "F-16C")
        const match = pilotName.match(/^([^#]+)/);
        return match ? match[1].trim() : 'Unknown';
    }
    
    /**
     * SVG Creation and Setup
     */
    createSVG() {
        const container = d3.select(`#${this.containerId}`);
        container.selectAll("*").remove(); // Clear previous
        
        this.width = container.node()?.clientWidth || 800;
        this.height = 600;
        
        this.svg = container.append("svg")
            .attr("width", "100%")
            .attr("height", this.height)
            .attr("viewBox", `0 0 ${this.width} ${this.height}`)
            .style("border", "1px solid #e2e8f0")
            .style("border-radius", "8px")
            .style("background", "linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)");
        
        // Add arrow markers for link direction
        this.svg.append("defs").selectAll("marker")
            .data(["air_to_air", "air_to_ground"])
            .enter().append("marker")
            .attr("id", d => `arrowhead_${d}`)
            .attr("viewBox", "0 -5 10 10")
            .attr("refX", 15)
            .attr("refY", 0)
            .attr("markerWidth", 6)
            .attr("markerHeight", 6)
            .attr("orient", "auto")
            .append("path")
            .attr("d", "M0,-5L10,0L0,5")
            .attr("fill", d => d === 'air_to_air' ? this.colors.airToAir : this.colors.airToGround);
    }
    
    /**
     * Physics Simulation Setup
     */
    setupSimulation() {
        const nodeArray = Array.from(this.nodes.values());
        
        this.simulation = d3.forceSimulation(nodeArray)
            .force("link", d3.forceLink(this.links)
                .id(d => d.id)
                .distance(120)
                .strength(0.8))
            .force("charge", d3.forceManyBody()
                .strength(-300)
                .distanceMax(400))
            .force("center", d3.forceCenter(this.width / 2, this.height / 2))
            .force("collision", d3.forceCollide()
                .radius(d => Math.max(15, 12 + d.kills * 2))
                .strength(0.7))
            .force("x", d3.forceX(this.width / 2).strength(0.1))
            .force("y", d3.forceY(this.height / 2).strength(0.1));
    }
    
    /**
     * Main Rendering Function
     */
    render() {
        if (this.nodes.size === 0) {
            this.renderEmptyState();
            return;
        }
        
        this.renderLinks();
        this.renderNodes();
        this.renderLabels();
        this.startSimulation();
        this.renderLegend();
    }
    
    renderEmptyState() {
        this.svg.append("text")
            .attr("x", this.width / 2)
            .attr("y", this.height / 2 - 20)
            .attr("text-anchor", "middle")
            .style("font-size", "18px")
            .style("font-weight", "bold")
            .style("fill", "#4a5568")
            .text("No Combat Data Available");
            
        this.svg.append("text")
            .attr("x", this.width / 2)
            .attr("y", this.height / 2 + 10)
            .attr("text-anchor", "middle")
            .style("font-size", "14px")
            .style("fill", "#718096")
            .text("No air-to-air or air-to-ground engagements found in this mission");
    }
    
    renderLinks() {
        this.linkElements = this.svg.append("g")
            .attr("class", "links")
            .selectAll("line")
            .data(this.links)
            .enter().append("line")
            .attr("stroke", d => d.type === 'air_to_air' ? this.colors.airToAir : this.colors.airToGround)
            .attr("stroke-opacity", 0.8)
            .attr("stroke-width", 2)
            .attr("marker-end", d => `url(#arrowhead_${d.type})`)
            .style("cursor", "pointer");
        
        // Add link tooltips
        this.linkElements.append("title")
            .text(d => {
                const sourceNode = this.nodes.get(d.source.id || d.source);
                const targetNode = this.nodes.get(d.target.id || d.target);
                return `${sourceNode?.id || d.source} → ${targetNode?.id || d.target}\n` +
                       `Weapon: ${d.weapon}\n` +
                       `Time: ${this.formatTime(d.time)}\n` +
                       `Type: ${d.type.replace('_', '-').toUpperCase()}`;
            });
    }
    
    renderNodes() {
        const nodeArray = Array.from(this.nodes.values());
        
        this.nodeElements = this.svg.append("g")
            .attr("class", "nodes")
            .selectAll("circle")
            .data(nodeArray)
            .enter().append("circle")
            .attr("r", d => d.type === 'pilot' ? Math.max(8, 10 + d.kills * 2) : 12)
            .attr("fill", d => this.getNodeColor(d))
            .attr("stroke", "#fff")
            .attr("stroke-width", 2)
            .style("cursor", "pointer")
            .call(this.createDragBehavior());
        
        // Add node tooltips
        this.nodeElements.append("title")
            .text(d => this.createNodeTooltip(d));
    }
    
    renderLabels() {
        const nodeArray = Array.from(this.nodes.values());
        
        this.labelElements = this.svg.append("g")
            .attr("class", "labels")
            .selectAll("text")
            .data(nodeArray)
            .enter().append("text")
            .text(d => d.type === 'pilot' ? d.aircraft : d.target_type)
            .style("font-size", "10px")
            .style("font-weight", "bold")
            .style("fill", "#2d3748")
            .style("text-anchor", "middle")
            .style("pointer-events", "none")
            .style("user-select", "none");
    }
    
    renderLegend() {
        const legend = this.svg.append("g")
            .attr("class", "legend")
            .attr("transform", `translate(${this.width - 200}, 20)`);
        
        const legendData = [
            { type: "Blue Coalition", color: this.colors.primary, symbol: "circle" },
            { type: "Red Coalition", color: this.colors.danger, symbol: "circle" },
            { type: "Ground Targets", color: this.colors.ground, symbol: "circle" },
            { type: "Air-to-Air Kills", color: this.colors.airToAir, symbol: "line" },
            { type: "Air-to-Ground Kills", color: this.colors.airToGround, symbol: "line" }
        ];
        
        const legendItems = legend.selectAll(".legend-item")
            .data(legendData)
            .enter().append("g")
            .attr("class", "legend-item")
            .attr("transform", (d, i) => `translate(0, ${i * 25})`);
        
        legendItems.append("rect")
            .attr("width", 180)
            .attr("height", 20)
            .attr("fill", "rgba(255,255,255,0.9)")
            .attr("stroke", "#e2e8f0")
            .attr("rx", 3);
        
        legendItems.each(function(d) {
            const item = d3.select(this);
            if (d.symbol === "circle") {
                item.append("circle")
                    .attr("cx", 10)
                    .attr("cy", 10)
                    .attr("r", 6)
                    .attr("fill", d.color);
            } else {
                item.append("line")
                    .attr("x1", 4)
                    .attr("y1", 10)
                    .attr("x2", 16)
                    .attr("y2", 10)
                    .attr("stroke", d.color)
                    .attr("stroke-width", 3);
            }
        });
        
        legendItems.append("text")
            .attr("x", 25)
            .attr("y", 14)
            .style("font-size", "12px")
            .style("fill", "#2d3748")
            .text(d => d.type);
    }
    
    /**
     * Simulation and Animation
     */
    startSimulation() {
        this.simulation.on("tick", () => {
            // Update link positions
            this.linkElements
                .attr("x1", d => Math.max(20, Math.min(this.width - 20, d.source.x)))
                .attr("y1", d => Math.max(20, Math.min(this.height - 20, d.source.y)))
                .attr("x2", d => Math.max(20, Math.min(this.width - 20, d.target.x)))
                .attr("y2", d => Math.max(20, Math.min(this.height - 20, d.target.y)));
            
            // Update node positions with boundary constraints
            this.nodeElements
                .attr("cx", d => {
                    d.x = Math.max(20, Math.min(this.width - 20, d.x));
                    return d.x;
                })
                .attr("cy", d => {
                    d.y = Math.max(20, Math.min(this.height - 20, d.y));
                    return d.y;
                });
            
            // Update label positions
            this.labelElements
                .attr("x", d => d.x)
                .attr("y", d => d.y + 25);
        });
        
        // Stop simulation after stabilization
        setTimeout(() => {
            this.simulation.alphaTarget(0);
        }, 5000);
    }
    
    /**
     * Interactive Features
     */
    createDragBehavior() {
        return d3.drag()
            .on("start", (event, d) => {
                if (!event.active) this.simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            })
            .on("drag", (event, d) => {
                d.fx = event.x;
                d.fy = event.y;
            })
            .on("end", (event, d) => {
                if (!event.active) this.simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            });
    }
    
    /**
     * Event Handling System
     */
    setupEventHandlers() {
        // Window resize handling
        window.addEventListener('resize', () => {
            if (document.getElementById(this.containerId).offsetParent !== null) {
                this.handleResize();
            }
        });
        
        // Node click events
        this.nodeElements?.on('click', (event, d) => {
            this.highlightNode(d);
        });
        
        // Link click events
        this.linkElements?.on('click', (event, d) => {
            this.highlightLink(d);
        });
    }
    
    handleResize() {
        const container = d3.select(`#${this.containerId}`);
        const newWidth = container.node()?.clientWidth || 800;
        
        if (Math.abs(newWidth - this.width) > 50) {
            this.width = newWidth;
            this.svg.attr("viewBox", `0 0 ${this.width} ${this.height}`);
            this.simulation?.force("center", d3.forceCenter(this.width / 2, this.height / 2));
            this.simulation?.alpha(0.3).restart();
        }
    }
    
    highlightNode(node) {
        // Reset all nodes
        this.nodeElements.style("opacity", 0.3);
        this.linkElements.style("opacity", 0.1);
        
        // Highlight selected node and connected elements
        this.nodeElements.filter(d => d.id === node.id).style("opacity", 1);
        
        this.linkElements
            .filter(d => d.source.id === node.id || d.target.id === node.id)
            .style("opacity", 1);
        
        // Reset after 3 seconds
        setTimeout(() => {
            this.nodeElements.style("opacity", 1);
            this.linkElements.style("opacity", 0.8);
        }, 3000);
    }
    
    highlightLink(link) {
        // Highlight link and connected nodes
        this.linkElements.style("opacity", 0.1);
        this.nodeElements.style("opacity", 0.3);
        
        this.linkElements.filter(d => d.id === link.id).style("opacity", 1);
        this.nodeElements
            .filter(d => d.id === link.source.id || d.id === link.target.id)
            .style("opacity", 1);
        
        // Reset after 3 seconds
        setTimeout(() => {
            this.nodeElements.style("opacity", 1);
            this.linkElements.style("opacity", 0.8);
        }, 3000);
    }
    
    /**
     * Network Analytics
     */
    updateAnalytics() {
        const nodeArray = Array.from(this.nodes.values());
        const maxPossibleLinks = nodeArray.length > 1 ? nodeArray.length * (nodeArray.length - 1) / 2 : 0;
        const density = maxPossibleLinks > 0 ? (this.links.length / maxPossibleLinks) : 0;
        
        const topKiller = nodeArray.reduce((max, pilot) => 
            (pilot.kills || 0) > (max.kills || 0) ? pilot : max, {kills: 0, id: 'None'});
        
        const stats = {
            nodes: nodeArray.length,
            links: this.links.length,
            density: (density * 100).toFixed(1),
            topKiller: topKiller.id,
            topKillerScore: topKiller.kills || 0
        };
        
        this.displayAnalytics(stats);
    }
    
    displayAnalytics(stats) {
        const analyticsDiv = d3.select(`#${this.containerId}`)
            .append("div")
            .attr("class", "network-analytics")
            .style("position", "absolute")
            .style("top", "10px")
            .style("left", "10px")
            .style("background", "rgba(255,255,255,0.95)")
            .style("padding", "10px")
            .style("border-radius", "5px")
            .style("border", "1px solid #e2e8f0")
            .style("font-size", "12px")
            .style("color", "#2d3748");
        
        analyticsDiv.html(`
            <strong>Network Statistics:</strong><br>
            Nodes: ${stats.nodes}<br>
            Links: ${stats.links}<br>
            Density: ${stats.density}%<br>
            Top Killer: ${stats.topKiller} (${stats.topKillerScore} kills)
        `);
    }
    
    /**
     * Utility Functions
     */
    getNodeColor(node) {
        if (node.type === 'ground_target') return this.colors.ground;
        return node.coalition === 1 ? this.colors.danger : this.colors.primary;
    }
    
    createNodeTooltip(node) {
        if (node.type === 'pilot') {
            const coalitionName = node.coalition === 1 ? 'Red' : node.coalition === 2 ? 'Blue' : 'Neutral';
            return `${node.id}\nAircraft: ${node.aircraft}\nKills: ${node.kills || 0}\nDeaths: ${node.deaths || 0}\nCoalition: ${coalitionName}`;
        } else {
            return `${node.target_type}\nDestroyed by: ${node.destroyed_by}\nTime: ${this.formatTime(node.time)}`;
        }
    }
    
    formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.floor(seconds % 60);
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    }
    
    /**
     * Public API
     */
    destroy() {
        if (this.simulation) {
            this.simulation.stop();
        }
        d3.select(`#${this.containerId}`).selectAll("*").remove();
    }
    
    updateData(newData) {
        this.data = newData;
        this.nodes.clear();
        this.links = [];
        this.init();
    }
}

/**
 * Global function to create kill network
 * Called by the dashboard when the network tab is activated
 */
function createKillNetwork() {
    try {
        const networkDiv = document.getElementById('killNetwork');
        if (!networkDiv) {
            console.error('Kill network container not found');
            return;
        }
        
        // Get analysis data from global scope
        const analysisData = window.analysisData || {};
        
        // Clear any existing network
        d3.select('#killNetwork').selectAll("*").remove();
        
        // Create new network instance
        window.killNetworkInstance = new KillNetwork('killNetwork', analysisData);
        
        console.log('Kill network created successfully');
        
    } catch (error) {
        console.error('Error creating kill network:', error);
        
        // Fallback error display
        const networkDiv = d3.select('#killNetwork');
        networkDiv.selectAll("*").remove();
        
        networkDiv.append("div")
            .style("text-align", "center")
            .style("padding", "50px")
            .style("color", "#e53e3e")
            .html(`
                <i class="fas fa-exclamation-triangle fa-3x mb-3"></i><br>
                <strong>Error Creating Kill Network</strong><br>
                <small>${error.message}</small>
            `);
    }
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { KillNetwork, createKillNetwork };
} 