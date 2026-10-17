#include "route_graph.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
static int index_of(const RouteGraph*g,int id){if(!g)return -1;for(int i=0;i<g->count;i++)if(g->nodes[i].id==id)return i;return -1;}
void route_graph_init(RouteGraph*g){if(g){g->count=0;for(int i=0;i<ROUTE_MAX_NODES;i++)g->nodes[i].edges=NULL;}}
int route_add_location(RouteGraph*g,int id,const char*name){if(!g||!name||id<=0||g->count>=ROUTE_MAX_NODES||index_of(g,id)>=0)return 0;RouteNode*n=&g->nodes[g->count++];n->id=id;n->edges=NULL;snprintf(n->name,sizeof n->name,"%s",name);return 1;}
static int add_edge(RouteNode*n,int to,int d){RouteEdge*e=(RouteEdge*)malloc(sizeof *e);if(!e)return 0;e->to=to;e->distance=d;e->next=n->edges;n->edges=e;return 1;}
int route_add_road(RouteGraph*g,int a,int b,int d,int bi){int i=index_of(g,a),j=index_of(g,b);if(i<0||j<0||a==b||d<=0)return 0;if(!add_edge(&g->nodes[i],b,d))return 0;if(bi&&!add_edge(&g->nodes[j],a,d)){RouteEdge*e=g->nodes[i].edges;g->nodes[i].edges=e->next;free(e);return 0;}return 1;}
int route_shortest_path(const RouteGraph*g,int start,int end,int*out,int cap,int*distout){if(!g||!out||cap<=0)return 0;int s=index_of(g,start),t=index_of(g,end);if(s<0||t<0)return 0;int d[ROUTE_MAX_NODES],prev[ROUTE_MAX_NODES],used[ROUTE_MAX_NODES]={0};for(int i=0;i<g->count;i++){d[i]=ROUTE_INF;prev[i]=-1;}d[s]=0;for(int step=0;step<g->count;step++){int u=-1;for(int i=0;i<g->count;i++)if(!used[i]&&(u<0||d[i]<d[u]))u=i;if(u<0||d[u]==ROUTE_INF)break;used[u]=1;if(u==t)break;for(RouteEdge*e=g->nodes[u].edges;e;e=e->next){int v=index_of(g,e->to);if(v>=0&&d[u]<=ROUTE_INF-e->distance&&d[u]+e->distance<d[v]){d[v]=d[u]+e->distance;prev[v]=u;}}}if(d[t]==ROUTE_INF)return 0;int rev[ROUTE_MAX_NODES],n=0;for(int cur=t;cur!=-1;cur=prev[cur]){if(n>=ROUTE_MAX_NODES)return 0;rev[n++]=g->nodes[cur].id;}if(n>cap)return 0;for(int i=0;i<n;i++)out[i]=rev[n-1-i];if(distout)*distout=d[t];return n;}
void route_graph_free(RouteGraph*g){if(!g)return;for(int i=0;i<g->count;i++){RouteEdge*e=g->nodes[i].edges;while(e){RouteEdge*n=e->next;free(e);e=n;}g->nodes[i].edges=NULL;}g->count=0;}
