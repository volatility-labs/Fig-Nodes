# Fig Nodes Cloud Migration - Implementation Guide

This guide provides concrete code examples and step-by-step instructions for migrating Fig Nodes to a cloud-based multi-user platform.

---

## Table of Contents

1. [Authentication Setup](#1-authentication-setup)
2. [Database Schema & Models](#2-database-schema--models)
3. [API Endpoints](#3-api-endpoints)
4. [Cloud Deployment](#4-cloud-deployment)
5. [Frontend Changes](#5-frontend-changes)
6. [Billing Integration](#6-billing-integration)
7. [Monitoring & Observability](#7-monitoring--observability)

---

## 1. Authentication Setup

### Option A: Auth0 (Recommended)

**Why Auth0:**
- Easy to set up
- Handles OAuth, SSO, MFA
- Generous free tier
- Enterprise-ready

**Setup Steps:**

1. **Install dependencies:**
```bash
uv add authlib python-jose[cryptography]
```

2. **Create authentication service:**

```python
# server/auth/auth_service.py
from typing import Optional
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import httpx

security = HTTPBearer()

class AuthService:
    def __init__(self, auth0_domain: str, api_audience: str):
        self.domain = auth0_domain
        self.audience = api_audience
        self.issuer = f"https://{auth0_domain}/"
        self.algorithms = ["RS256"]
        self._jwks_client = None
    
    async def get_jwks(self):
        """Fetch JSON Web Key Set from Auth0"""
        if not self._jwks_client:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.issuer}.well-known/jwks.json")
                self._jwks_client = response.json()
        return self._jwks_client
    
    async def verify_token(self, token: str) -> dict:
        """Verify JWT token and return user info"""
        try:
            jwks = await self.get_jwks()
            unverified_header = jwt.get_unverified_header(token)
            
            rsa_key = {}
            for key in jwks["keys"]:
                if key["kid"] == unverified_header["kid"]:
                    rsa_key = {
                        "kty": key["kty"],
                        "kid": key["kid"],
                        "use": key["use"],
                        "n": key["n"],
                        "e": key["e"]
                    }
            
            if not rsa_key:
                raise HTTPException(401, "Unable to find appropriate key")
            
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=self.algorithms,
                audience=self.audience,
                issuer=self.issuer,
            )
            return payload
        
        except JWTError as e:
            raise HTTPException(401, f"Invalid token: {str(e)}")
    
    async def get_current_user(
        self,
        credentials: HTTPAuthorizationCredentials = Security(security)
    ) -> dict:
        """FastAPI dependency for protected routes"""
        token = credentials.credentials
        return await self.verify_token(token)


# Initialize in server/server.py
from server.auth.auth_service import AuthService
import os

auth_service = AuthService(
    auth0_domain=os.getenv("AUTH0_DOMAIN"),
    api_audience=os.getenv("AUTH0_AUDIENCE")
)
```

3. **Environment variables:**
```bash
# .env
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_AUDIENCE=https://api.fignodes.com
AUTH0_CLIENT_ID=your-client-id
AUTH0_CLIENT_SECRET=your-client-secret
```

4. **Protect routes:**
```python
# server/api/v1/graphs.py
from fastapi import APIRouter, Depends
from server.auth.auth_service import auth_service

router = APIRouter()

@router.get("/api/v1/graphs")
async def list_graphs(user = Depends(auth_service.get_current_user)):
    user_id = user["sub"]  # Auth0 user ID
    # Fetch graphs for this user
    return {"graphs": [...]}
```

### Option B: Firebase Auth

```python
# server/auth/firebase_auth.py
from firebase_admin import credentials, initialize_app, auth
from fastapi import HTTPException

cred = credentials.Certificate("path/to/serviceAccountKey.json")
initialize_app(cred)

async def verify_firebase_token(token: str):
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        raise HTTPException(401, f"Invalid token: {str(e)}")
```

---

## 2. Database Schema & Models

### Setup PostgreSQL

1. **Install dependencies:**
```bash
uv add asyncpg sqlalchemy[asyncio] alembic
```

2. **Database models:**

```python
# server/db/models.py
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    auth_id = Column(String, unique=True, nullable=False)  # Auth0/Firebase ID
    email = Column(String, unique=True, nullable=False)
    display_name = Column(String)
    tier = Column(String, default="free")  # free, pro, enterprise
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Workspace(Base):
    __tablename__ = "workspaces"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Graph(Base):
    __tablename__ = "graphs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)
    data = Column(JSON, nullable=False)  # Your current graph JSON
    version = Column(Integer, default=1)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class GraphVersion(Base):
    """Store graph history for version control"""
    __tablename__ = "graph_versions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    graph_id = Column(UUID(as_uuid=True), ForeignKey("graphs.id", ondelete="CASCADE"))
    version = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)
    commit_message = Column(Text)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Execution(Base):
    __tablename__ = "executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    graph_id = Column(UUID(as_uuid=True), ForeignKey("graphs.id", ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    status = Column(String, default="pending")  # pending, running, completed, failed
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    error = Column(Text)
    results = Column(JSON)

class SharedGraph(Base):
    """Sharing permissions for graphs"""
    __tablename__ = "shared_graphs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    graph_id = Column(UUID(as_uuid=True), ForeignKey("graphs.id", ondelete="CASCADE"))
    shared_with_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    permission = Column(String, default="read")  # read, write, admin
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

3. **Database connection:**

```python
# server/db/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/fignodes")

engine = create_async_engine(DATABASE_URL, echo=True)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
```

4. **Initialize with Alembic:**

```bash
# Initialize Alembic
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Initial schema"

# Apply migration
alembic upgrade head
```

---

## 3. API Endpoints

### Graph Management API

```python
# server/api/v1/graphs.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from server.db.database import get_db
from server.db.models import Graph, Workspace, GraphVersion
from server.auth.auth_service import auth_service
from pydantic import BaseModel
from typing import Optional
import uuid

router = APIRouter(prefix="/api/v1", tags=["graphs"])

class GraphCreate(BaseModel):
    workspace_id: str
    name: str
    data: dict

class GraphUpdate(BaseModel):
    name: Optional[str] = None
    data: Optional[dict] = None
    commit_message: Optional[str] = None

@router.get("/workspaces")
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    user = Depends(auth_service.get_current_user)
):
    """List all workspaces for current user"""
    user_id = user["sub"]
    
    result = await db.execute(
        select(Workspace).where(Workspace.user_id == user_id)
    )
    workspaces = result.scalars().all()
    
    return {"workspaces": [
        {
            "id": str(w.id),
            "name": w.name,
            "description": w.description,
            "created_at": w.created_at.isoformat(),
        }
        for w in workspaces
    ]}

@router.post("/workspaces")
async def create_workspace(
    name: str,
    description: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user = Depends(auth_service.get_current_user)
):
    """Create a new workspace"""
    workspace = Workspace(
        user_id=uuid.UUID(user["sub"]),
        name=name,
        description=description
    )
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
    
    return {"workspace": {"id": str(workspace.id), "name": workspace.name}}

@router.get("/workspaces/{workspace_id}/graphs")
async def list_graphs(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    user = Depends(auth_service.get_current_user)
):
    """List all graphs in a workspace"""
    # Verify user owns workspace
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == uuid.UUID(workspace_id),
            Workspace.user_id == uuid.UUID(user["sub"])
        )
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(404, "Workspace not found")
    
    # Get graphs
    result = await db.execute(
        select(Graph).where(Graph.workspace_id == uuid.UUID(workspace_id))
    )
    graphs = result.scalars().all()
    
    return {"graphs": [
        {
            "id": str(g.id),
            "name": g.name,
            "version": g.version,
            "created_at": g.created_at.isoformat(),
            "updated_at": g.updated_at.isoformat(),
        }
        for g in graphs
    ]}

@router.post("/graphs")
async def create_graph(
    graph_data: GraphCreate,
    db: AsyncSession = Depends(get_db),
    user = Depends(auth_service.get_current_user)
):
    """Create a new graph"""
    # Verify user owns workspace
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == uuid.UUID(graph_data.workspace_id),
            Workspace.user_id == uuid.UUID(user["sub"])
        )
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(404, "Workspace not found")
    
    graph = Graph(
        workspace_id=uuid.UUID(graph_data.workspace_id),
        name=graph_data.name,
        data=graph_data.data,
        version=1
    )
    db.add(graph)
    await db.commit()
    await db.refresh(graph)
    
    return {"graph": {"id": str(graph.id), "name": graph.name}}

@router.get("/graphs/{graph_id}")
async def get_graph(
    graph_id: str,
    db: AsyncSession = Depends(get_db),
    user = Depends(auth_service.get_current_user)
):
    """Get a specific graph"""
    result = await db.execute(
        select(Graph)
        .join(Workspace)
        .where(
            Graph.id == uuid.UUID(graph_id),
            Workspace.user_id == uuid.UUID(user["sub"])
        )
    )
    graph = result.scalar_one_or_none()
    if not graph:
        raise HTTPException(404, "Graph not found")
    
    return {
        "graph": {
            "id": str(graph.id),
            "name": graph.name,
            "data": graph.data,
            "version": graph.version,
            "created_at": graph.created_at.isoformat(),
            "updated_at": graph.updated_at.isoformat(),
        }
    }

@router.put("/graphs/{graph_id}")
async def update_graph(
    graph_id: str,
    update_data: GraphUpdate,
    db: AsyncSession = Depends(get_db),
    user = Depends(auth_service.get_current_user)
):
    """Update a graph (with versioning)"""
    result = await db.execute(
        select(Graph)
        .join(Workspace)
        .where(
            Graph.id == uuid.UUID(graph_id),
            Workspace.user_id == uuid.UUID(user["sub"])
        )
    )
    graph = result.scalar_one_or_none()
    if not graph:
        raise HTTPException(404, "Graph not found")
    
    # Save version history if data changed
    if update_data.data is not None:
        version = GraphVersion(
            graph_id=graph.id,
            version=graph.version,
            data=graph.data,
            commit_message=update_data.commit_message,
            created_by=uuid.UUID(user["sub"])
        )
        db.add(version)
        
        graph.data = update_data.data
        graph.version += 1
    
    if update_data.name is not None:
        graph.name = update_data.name
    
    await db.commit()
    await db.refresh(graph)
    
    return {"graph": {"id": str(graph.id), "version": graph.version}}

@router.delete("/graphs/{graph_id}")
async def delete_graph(
    graph_id: str,
    db: AsyncSession = Depends(get_db),
    user = Depends(auth_service.get_current_user)
):
    """Delete a graph"""
    result = await db.execute(
        select(Graph)
        .join(Workspace)
        .where(
            Graph.id == uuid.UUID(graph_id),
            Workspace.user_id == uuid.UUID(user["sub"])
        )
    )
    graph = result.scalar_one_or_none()
    if not graph:
        raise HTTPException(404, "Graph not found")
    
    await db.delete(graph)
    await db.commit()
    
    return {"success": True}

@router.get("/graphs/{graph_id}/versions")
async def list_graph_versions(
    graph_id: str,
    db: AsyncSession = Depends(get_db),
    user = Depends(auth_service.get_current_user)
):
    """List all versions of a graph"""
    # Verify access
    result = await db.execute(
        select(Graph)
        .join(Workspace)
        .where(
            Graph.id == uuid.UUID(graph_id),
            Workspace.user_id == uuid.UUID(user["sub"])
        )
    )
    graph = result.scalar_one_or_none()
    if not graph:
        raise HTTPException(404, "Graph not found")
    
    # Get versions
    result = await db.execute(
        select(GraphVersion)
        .where(GraphVersion.graph_id == uuid.UUID(graph_id))
        .order_by(GraphVersion.version.desc())
    )
    versions = result.scalars().all()
    
    return {"versions": [
        {
            "version": v.version,
            "commit_message": v.commit_message,
            "created_at": v.created_at.isoformat(),
        }
        for v in versions
    ]}

@router.post("/graphs/{graph_id}/restore/{version}")
async def restore_graph_version(
    graph_id: str,
    version: int,
    db: AsyncSession = Depends(get_db),
    user = Depends(auth_service.get_current_user)
):
    """Restore a graph to a previous version"""
    # Verify access
    result = await db.execute(
        select(Graph)
        .join(Workspace)
        .where(
            Graph.id == uuid.UUID(graph_id),
            Workspace.user_id == uuid.UUID(user["sub"])
        )
    )
    graph = result.scalar_one_or_none()
    if not graph:
        raise HTTPException(404, "Graph not found")
    
    # Get version data
    result = await db.execute(
        select(GraphVersion).where(
            GraphVersion.graph_id == uuid.UUID(graph_id),
            GraphVersion.version == version
        )
    )
    old_version = result.scalar_one_or_none()
    if not old_version:
        raise HTTPException(404, "Version not found")
    
    # Save current as version
    current_version = GraphVersion(
        graph_id=graph.id,
        version=graph.version,
        data=graph.data,
        commit_message=f"Before restoring to version {version}",
        created_by=uuid.UUID(user["sub"])
    )
    db.add(current_version)
    
    # Restore old data
    graph.data = old_version.data
    graph.version += 1
    
    await db.commit()
    
    return {"success": True, "new_version": graph.version}
```

---

## 4. Cloud Deployment

### Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for frontend build
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g yarn

# Install uv
RUN pip install uv

# Copy backend files
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

# Copy frontend files and build
COPY frontend ./frontend
WORKDIR /app/frontend
RUN yarn install --frozen-lockfile
RUN yarn build

# Copy rest of application
WORKDIR /app
COPY . .

# Expose port
EXPOSE 8000

# Start server in production mode
CMD ["uv", "run", "python", "main.py", "--prod", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose (Local Development)

```yaml
# docker-compose.yml
version: '3.8'

services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: fignodes
      POSTGRES_PASSWORD: fignodes_dev
      POSTGRES_DB: fignodes
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://fignodes:fignodes_dev@db:5432/fignodes
      REDIS_URL: redis://redis:6379/0
      AUTH0_DOMAIN: ${AUTH0_DOMAIN}
      AUTH0_AUDIENCE: ${AUTH0_AUDIENCE}
    depends_on:
      - db
      - redis
    volumes:
      - ./:/app
    command: uv run python main.py --dev

volumes:
  postgres_data:
```

### AWS Deployment (ECS)

```yaml
# aws-task-definition.json
{
  "family": "fignodes-app",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "fignodes",
      "image": "your-ecr-repo/fignodes:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "DATABASE_URL",
          "value": "postgresql+asyncpg://..."
        },
        {
          "name": "AUTH0_DOMAIN",
          "value": "your-tenant.auth0.com"
        }
      ],
      "secrets": [
        {
          "name": "AUTH0_CLIENT_SECRET",
          "valueFrom": "arn:aws:secretsmanager:..."
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/fignodes",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### Kubernetes Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fignodes-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: fignodes
  template:
    metadata:
      labels:
        app: fignodes
    spec:
      containers:
      - name: fignodes
        image: your-registry/fignodes:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: fignodes-secrets
              key: database-url
        - name: AUTH0_DOMAIN
          valueFrom:
            configMapKeyRef:
              name: fignodes-config
              key: auth0-domain
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: fignodes-service
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8000
  selector:
    app: fignodes
```

---

## 5. Frontend Changes

### API Client

```typescript
// frontend/services/CloudAPIClient.ts
export interface GraphListItem {
  id: string;
  name: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface Graph {
  id: string;
  name: string;
  data: any; // Your graph JSON
  version: number;
  created_at: string;
  updated_at: string;
}

export class CloudAPIClient {
  private baseURL: string;
  private token: string | null = null;

  constructor(baseURL: string = '') {
    this.baseURL = baseURL || window.location.origin;
  }

  setToken(token: string) {
    this.token = token;
    localStorage.setItem('auth_token', token);
  }

  getToken(): string | null {
    if (!this.token) {
      this.token = localStorage.getItem('auth_token');
    }
    return this.token;
  }

  private async fetch(path: string, options: RequestInit = {}): Promise<Response> {
    const token = this.getToken();
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseURL}${path}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      // Token expired, redirect to login
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }

    return response;
  }

  async listWorkspaces() {
    const response = await this.fetch('/api/v1/workspaces');
    return response.json();
  }

  async createWorkspace(name: string, description?: string) {
    const response = await this.fetch('/api/v1/workspaces', {
      method: 'POST',
      body: JSON.stringify({ name, description }),
    });
    return response.json();
  }

  async listGraphs(workspaceId: string): Promise<{ graphs: GraphListItem[] }> {
    const response = await this.fetch(`/api/v1/workspaces/${workspaceId}/graphs`);
    return response.json();
  }

  async getGraph(graphId: string): Promise<{ graph: Graph }> {
    const response = await this.fetch(`/api/v1/graphs/${graphId}`);
    return response.json();
  }

  async createGraph(workspaceId: string, name: string, data: any) {
    const response = await this.fetch('/api/v1/graphs', {
      method: 'POST',
      body: JSON.stringify({ workspace_id: workspaceId, name, data }),
    });
    return response.json();
  }

  async updateGraph(graphId: string, data: any, commitMessage?: string) {
    const response = await this.fetch(`/api/v1/graphs/${graphId}`, {
      method: 'PUT',
      body: JSON.stringify({ data, commit_message: commitMessage }),
    });
    return response.json();
  }

  async deleteGraph(graphId: string) {
    const response = await this.fetch(`/api/v1/graphs/${graphId}`, {
      method: 'DELETE',
    });
    return response.json();
  }

  async listGraphVersions(graphId: string) {
    const response = await this.fetch(`/api/v1/graphs/${graphId}/versions`);
    return response.json();
  }

  async restoreGraphVersion(graphId: string, version: number) {
    const response = await this.fetch(`/api/v1/graphs/${graphId}/restore/${version}`, {
      method: 'POST',
    });
    return response.json();
  }
}

export const cloudAPI = new CloudAPIClient();
```

### Update FileManager for Cloud

```typescript
// frontend/services/CloudFileManager.ts
import { FileManager } from './FileManager';
import { cloudAPI } from './CloudAPIClient';
import { LGraph, LGraphCanvas } from '@fig-node/litegraph';

export class CloudFileManager extends FileManager {
  private currentGraphId: string | null = null;
  private currentWorkspaceId: string | null = null;
  private autoSaveInterval: number | null = null;

  constructor(graph: LGraph, canvas: LGraphCanvas) {
    super(graph, canvas);
    
    // Auto-save to cloud every 30 seconds
    this.startAutoSave();
  }

  private startAutoSave() {
    this.autoSaveInterval = window.setInterval(() => {
      if (this.currentGraphId) {
        this.saveToCloud();
      }
    }, 30000); // 30 seconds
  }

  async loadFromCloud(graphId: string) {
    try {
      const { graph: graphData } = await cloudAPI.getGraph(graphId);
      this.currentGraphId = graphId;
      
      // Load graph data into Litegraph
      (this.graph as any).configure(graphData.data);
      (this.canvas as any).draw(true, true);
      
      this.updateGraphName(graphData.name);
      
      console.log(`✅ Loaded graph from cloud: ${graphData.name}`);
    } catch (error) {
      console.error('❌ Failed to load graph from cloud:', error);
      throw error;
    }
  }

  async saveToCloud(commitMessage?: string) {
    if (!this.currentGraphId) {
      console.warn('No graph ID set, cannot save to cloud');
      return;
    }

    try {
      const graphData = (this.graph as any).serialize();
      
      await cloudAPI.updateGraph(this.currentGraphId, graphData, commitMessage);
      
      console.log('✅ Saved graph to cloud');
    } catch (error) {
      console.error('❌ Failed to save graph to cloud:', error);
      throw error;
    }
  }

  async createNewGraphInCloud(workspaceId: string, name: string) {
    try {
      const graphData = (this.graph as any).serialize();
      
      const { graph } = await cloudAPI.createGraph(workspaceId, name, graphData);
      this.currentGraphId = graph.id;
      this.currentWorkspaceId = workspaceId;
      
      this.updateGraphName(name);
      
      console.log(`✅ Created new graph in cloud: ${name}`);
    } catch (error) {
      console.error('❌ Failed to create graph in cloud:', error);
      throw error;
    }
  }

  setCurrentGraph(graphId: string, workspaceId: string) {
    this.currentGraphId = graphId;
    this.currentWorkspaceId = workspaceId;
  }

  stopAutoSave() {
    if (this.autoSaveInterval) {
      window.clearInterval(this.autoSaveInterval);
      this.autoSaveInterval = null;
    }
  }
}
```

### Auth Integration (Auth0)

```typescript
// frontend/services/AuthService.ts
import { Auth0Client } from '@auth0/auth0-spa-js';
import { cloudAPI } from './CloudAPIClient';

class AuthService {
  private auth0: Auth0Client | null = null;

  async initialize() {
    this.auth0 = new Auth0Client({
      domain: 'your-tenant.auth0.com',
      clientId: 'your-client-id',
      authorizationParams: {
        redirect_uri: window.location.origin,
        audience: 'https://api.fignodes.com',
      },
    });

    // Check if returning from Auth0 redirect
    const query = window.location.search;
    if (query.includes('code=') && query.includes('state=')) {
      await this.handleRedirectCallback();
    }

    // Check if already authenticated
    const isAuthenticated = await this.auth0.isAuthenticated();
    if (isAuthenticated) {
      const token = await this.auth0.getTokenSilently();
      cloudAPI.setToken(token);
    }
  }

  async login() {
    if (!this.auth0) throw new Error('Auth0 not initialized');
    await this.auth0.loginWithRedirect();
  }

  async logout() {
    if (!this.auth0) throw new Error('Auth0 not initialized');
    await this.auth0.logout({
      logoutParams: {
        returnTo: window.location.origin,
      },
    });
  }

  async getUser() {
    if (!this.auth0) return null;
    const isAuthenticated = await this.auth0.isAuthenticated();
    if (!isAuthenticated) return null;
    return this.auth0.getUser();
  }

  async isAuthenticated(): Promise<boolean> {
    if (!this.auth0) return false;
    return this.auth0.isAuthenticated();
  }

  private async handleRedirectCallback() {
    if (!this.auth0) return;
    
    try {
      const result = await this.auth0.handleRedirectCallback();
      const token = await this.auth0.getTokenSilently();
      cloudAPI.setToken(token);
      
      // Clean up URL
      window.history.replaceState({}, document.title, '/');
    } catch (error) {
      console.error('Error handling Auth0 redirect:', error);
    }
  }
}

export const authService = new AuthService();
```

---

## 6. Billing Integration

### Stripe Setup

```python
# server/billing/stripe_service.py
import stripe
import os
from fastapi import APIRouter, Depends, HTTPException
from server.auth.auth_service import auth_service

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

PRICE_IDS = {
    "pro_monthly": "price_1234567890",
    "pro_yearly": "price_0987654321",
}

@router.post("/create-checkout-session")
async def create_checkout_session(
    price_id: str,
    user = Depends(auth_service.get_current_user)
):
    """Create Stripe checkout session for subscription"""
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price": price_id,
                "quantity": 1,
            }],
            mode="subscription",
            success_url="https://fignodes.com/billing/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://fignodes.com/billing/cancel",
            client_reference_id=user["sub"],
            metadata={
                "user_id": user["sub"],
            },
        )
        return {"checkout_url": checkout_session.url}
    except Exception as e:
        raise HTTPException(400, str(e))

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
        )
    except Exception as e:
        raise HTTPException(400, str(e))
    
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session["metadata"]["user_id"]
        
        # Update user tier in database
        # ... (update User.tier to "pro")
        
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        user_id = subscription["metadata"]["user_id"]
        
        # Downgrade user tier
        # ... (update User.tier to "free")
    
    return {"success": True}

@router.get("/portal")
async def create_portal_session(
    user = Depends(auth_service.get_current_user)
):
    """Create Stripe customer portal session"""
    # Get user's Stripe customer ID from database
    # ...
    
    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url="https://fignodes.com/settings",
        )
        return {"portal_url": portal_session.url}
    except Exception as e:
        raise HTTPException(400, str(e))
```

---

## 7. Monitoring & Observability

### Health Check Endpoint

```python
# server/api/health.py
from fastapi import APIRouter
from server.db.database import engine

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check for load balancers"""
    try:
        # Check database connection
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        
        return {
            "status": "healthy",
            "database": "connected",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }
```

### Sentry Integration

```python
# server/monitoring/sentry.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
import os

def init_sentry():
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
        traces_sample_rate=0.1,  # 10% of transactions
        profiles_sample_rate=0.1,
    )
```

### Logging

```python
# server/monitoring/logging_config.py
import logging
import sys

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set log levels for third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
```

---

## Summary

This guide provides concrete implementations for:

1. ✅ **Authentication** (Auth0/Firebase)
2. ✅ **Database** (PostgreSQL with SQLAlchemy)
3. ✅ **API** (FastAPI endpoints for graph management)
4. ✅ **Deployment** (Docker, AWS ECS, Kubernetes)
5. ✅ **Frontend** (Cloud API client, Auth integration)
6. ✅ **Billing** (Stripe subscriptions)
7. ✅ **Monitoring** (Health checks, Sentry, logging)

**Next Steps:**

1. Set up Auth0 account
2. Create PostgreSQL database (RDS, Cloud SQL, or Supabase)
3. Implement API endpoints from this guide
4. Update frontend to use CloudAPIClient
5. Deploy to staging environment
6. Test end-to-end
7. Set up monitoring
8. Launch to production

**Timeline:** 3-6 months for full cloud deployment

**Remember:** Your Litegraph implementation is solid. Don't rewrite it - enhance it!

