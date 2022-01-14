%% Network Models 1: Basic Graph Models

%% 1. Graph Representations
%% Complete bipartite directed graph (or digraph)
C = [6 10; NaN 13; 9 16]; mdisp(C)
W = lev2adj(C)
%% Bipartite graph
W(4,1) = 6; W(5,3) = 3; W(3,4) = 0;
W
IJC = adj2list(W)
%% Multigraph
IJC = [
   1 -4 6
   1 -4 18
   1 5 10
   2 4 0
   2 5 13
   3 5 16
   3 5 3]
no_W = list2adj(IJC)
%% Complete multipartite directed graph
C12 = C; mdisp(C12)
C23 = [4 12 10; 15 11 14]; mdisp(C23)
W = lev2adj(C12,C23); mdisp(W)

%% 2. Transportation Problem (TRANS)
%% TRANS in ALA
help ala
%% TRANS w/ Inf Sup
clear all
C = [8 6 10 9; 9 12 13 7; 14 9 16 5];
mdisp(C)
argmin(C,1)
dem = [45 20 30 30]
F = full(sparse(argmin(C,1),1:length(dem),dem))
TC = C.*F
TC = sum(sum(C.*F))
%% TRANS w/ Sup Constraints
sum(F,2)
sup = [55 50 40]
sum(sup) >= sum(dem)  % feasibility check
mdisp([C sup(:); dem 0])
%% Greedy vs. Optimal Solution
[F,TC] = gtrans(C,sup,dem)

%% 3. Min Cost Network Flow Problem (MCNF): No Arc/Node Bounds
%% Create network
IJC = [
     1     2     2
     1     3     3
     2     4     4
     2     5     5
     3     5     1
     4     5     3];
s = [6 2 0 0 -8];
%% Convert to LP directly and solve
help lplog
[Aeq,c] = list2incid(IJC)
beq = s
[x,TC,XFlg,out] = lplog(c,[],[],Aeq,beq)
Aeq(end,:) = [];
beq(end) = [];
[x,TC,XFlg,out] = lplog(c,[],[],Aeq,beq)
%% Convert using MCNF2LP, solve, and report using LP2MCNF
lp = mcnf2lp(IJC,s);
[x,TC,XFlg,out] = lplog(lp{:})
[f,TC,nf] = lp2mcnf(x,IJC,s)
%% Use LINPROG to solve
help linprog
[x,TC,XFlg,out] = linprog(lp{:})
[f,TC,nf] = lp2mcnf(x,IJC,s)
%% Use Milp to creat LP instance
mp = Milp('MCNF');
mp.addobj('min',c)
mp.addcstr(Aeq,'=',beq)
lp = mp.milp2lp
mp.dispmodel
%% Use Gurobi to solve
clear mp params
mp = Milp('MCNF');
mp.lp2milp(lp{:})
model = mp.milp2gb
params.outputflag = 1;
result = gurobi(model, params);
x = result.x
TC = result.objval

%% 4. MCNF: Arcs/Nodes Bounds and Node Costs
%% Create network
IJCUL = [
     1     2     2   Inf     0
     1     3     3   Inf     0
     2     4     4     3     0
     2     5     5     9     0
     3     5     1     3     0
     4     5     3   Inf     1];
SCUL = [
     6 3 Inf 0
     6 1 Inf 0
     0 0 Inf 3
     0 2   4 0
    -8 0 Inf 0];
%% Solve
lp2 = mcnf2lp(IJCUL,SCUL);
[x,TC,XFlg,out] = lplog(lp2{:})
[f,TC,nf] = lp2mcnf(x,IJCUL,SCUL)
%% Display 
mp = Milp('MCNF');
mp.lp2milp(lp{:})
mp.dispmodel
mp.lp2milp(lp2{:})
mp.dispmodel

%% 5. TRANS as 2-level MCNF
%% Create MCNF inputs
W = lev2adj(C)
IJC = adj2list(W)
s = [sup -dem]
%% Solve
lp = mcnf2lp(IJC,s);
[x,TC,XFlg,out] = lplog(lp{:})
[f,TC,nf] = lp2mcnf(x,IJC,s)
%% Report
F
IJC
IJF = [IJC(:,[1 2]) f]
AF = list2adj(IJF)
F = adj2lev(AF,size(C))
TC = C.*F
TC = sum(sum(C.*F))

%% 6. Transshipment Problem: 3-level MCNF
%% Create MCNF inputs
C23=C
C12 = [4 6 5; 3 8 2]
W = lev2adj(C12,C23)
IJC = adj2list(W)
s = [65 80 0 0 0 -dem]
%% Solve
lp = mcnf2lp(IJC,s);
[x,TC,XFlg,out] = lplog(lp{:})
[f,TC,nf] = lp2mcnf(x,IJC,s)
%% Report
IJF = [IJC(:,[1 2]) f]
AF = list2adj(IJF)
F = adj2lev(AF,[3 4])    % Error
F = adj2lev(AF,[2 3 4])  % Error
[F12,F23] = adj2lev(AF,[2 3 4])
W = lev2adj(C12,C23);
mdisp(W)
