import { BaseCustomNode } from "../../base/BaseCustomNode";
import { LGraphNode } from "litegraph.js";

export default class VBPLevelFilterNodeUI extends BaseCustomNode {
    static nodeType = "VBPLevelFilter";

    constructor(node?: LGraphNode) {
        super(node);
        this.init();
    }

    init() {
        this.title = "VBP Level Filter";
        this.color = "#2c5530";
        this.bgcolor = "#1a3320";
    }
}

