% Make Routing 4: Min TLC Multi-Stop Routing

%% Example 1: 3 Shipments
%% Create Shipments
City = {'Raleigh','Athens','Asheville','Jacksonville',...
   'Savannah','Gainesville'};
ST = {'NC','GA','NC','FL','GA','FL'};
XY = uscity('XY',mand(City,uscity('Name'),ST,uscity('ST')));

D = dists(XY,XY,'mi')*1.2;
mdisp(D,City,City)

tr = struct('r',2,'Kwt',25,'Kcu',2750);

sh = vec2struct('f',[100 200 50],'s',[10 15 7],...
   'b',[1 3 5],'e',[2 4 6],'v',[500 200 800],'a',1,'h',.3);
sh = vec2struct(sh,'d',diag(D([sh.b],[sh.e])));
sdisp(sh)
plotshmt(sh,XY)
pplot(XY,City)

%% Min Distance
rTDh = @(rte) rteTC(rte,sh,D);
[r123,TD123] = insertimprove([1 2 3],rTDh,sh)
plotshmt(sh,XY,r123)
pplot(XY,City)
set(findobj(gca,'DisplayName','Route Label'),'FontSize',8),shg
%% Route has a mix of two loads 
ld = rte2ldmx(r123)
ld{:}
rTDh(r123)
%% Route X has a single load mix
rX = [1 2 3 3 2 1]
ld = rte2ldmx(rX)
ld{:}
rTDh(rX)
%% Independent: TL and LTL
ppi = [];   % Default 2004 LTL PPI (commensurate with $2/mi TL rate)
[TLC1,q1,isLTL] = minTLC(sh,tr,ppi);
sh = vec2struct(sh,'isLTL',isLTL);
vdisp('TLC1,q1,isLTL',true)

%% Consolidated shipments
rTLCh = @(rte) minTLC(sh,tr,ppi,D,rte);
%% Combine shipments 2 and 3
r23 = insertimprove([2 3],rTLCh,sh)
[TLC23,q23] = minTLC(sh,tr,ppi,D,r23)
idx = rte2idx(r23)
t23 = q23./[sh(idx).f]'
%% Add shipment 1 to consolidated route
r123 = mincostinsert([1 1],r23,rTLCh,sh)
[TLC123,q123] = minTLC(sh,tr,ppi,D,r123)
t123 = q123./[sh.f]'
%% Load mix
ld = rte2ldmx(r123)
ld{:}
%% How q is determined inside minTLC
ash = aggshmt(sh);
ash.d = rteTC(r123,sh,D)
q = sqrt((ash.d*tr.r*ash.f)/(ash.v*ash.h))
q = q*[sh.f]'/ash.f

k = 1  % k is min ratio of max payload to opt TL size of all load mixes 
for i = 1:length(ld)
   k = min(k, maxpayld(aggshmt(sh(ld{i})),tr)/sum(q(ld{i})))
end
q = k*q
%% Weight and cube of each load mix
Wt = cellfun(@(ldi)sum(q123(ldi)),ld);
cu = 2000*q123./[sh.s]';
Cube = cellfun(@(ldi)sum(cu(ldi)),ld);
vdisp('Wt,Cube')

%% Example 2. 30 Shipments
%% Create Data
clear, close all
load shmtNC30
tr = struct('r',2,'Kwt',25,'Kcu',2750);
sh = vec2struct('idx',1:length(b),'b',b,'e',e,'f',f,'s',s,'v',v,'a',.5,'h',.3);
sh = vec2struct(sh,'d',diag(D([sh.b],[sh.e])));
ppiLTL = [];
[TLC1,q1,isLTL] = minTLC(sh,tr,ppiLTL);
sh = vec2struct(sh,'TLC1',TLC1,'q1',q1,'t1',q1./[sh.f],'isLTL',isLTL);
qmax = maxpayld(sh,tr);
sh = vec2struct(sh,'qmax',qmax);
sdisp(sh)
%% Independent shipments
plotshmt(sh,XY,[],tr,true)
%% Consolidated shipments
rTCh = @(rte) minTLC(sh,tr,[],D,rte);
ph = @(rte) plotshmt(sh,XY,rte,tr);
IJS = pairwisesavings(rTCh,sh,minTLC(sh,tr));
%% Construct and improve routes
[rc,TLCc] = twoopt(savings(rTCh,sh,IJS,ph),rTCh,ph);
%% Make shipments not in routes into single-shipment routes
[rc,idx1,TLCc] = sh2rte(sh,rc,rTCh);
plotshmt(sh,XY,rc,tr)
%% Change in TLC from indep to consol:
100*(sum(TLCc) - sum(TLC1))/sum(TLC1)
%% Change in TLC for just multi-shipment routes
idxrte = find(cellfun(@length,rc) > 2);
idxsh = rte2idx(rc(idxrte));
idxsh = [idxsh{:}];
100*(sum(TLCc(idxrte)) - sum(TLC1(idxsh)))/sum(TLC1(idxsh))

%% Example 3: Allocation for Consolidation
%% 3 shipments (exact and approx Shapley allocation the same)
D = dijk(list2adj([1 -2 300; 3 -4 250; 5 -6 275; ...
   1 -3 30; 4 -2 30; 1 -5 60; 6 -2 60]));
mdisp(D)
sh = vec2struct('b',[1 3 5],'e',[2 4 6]);
sh = vec2struct(sh,'d',diag(D([sh.b],[sh.e])));
sdisp(sh,1)
r = 1
rTCh = @(rte) rteTC(rte,sh,D*r);
n = length(sh)
%% Independent transport charge
c0 = [sh.d]*r
%% Min incremental charge for all possible routes
R = perms(1:n)
R = sortrows(R,1:n)
C = zeros(size(R));
for i = 1:size(C,1)
   for j = 1:size(C,2)
      Rj = perms(R(i,1:j));  % Try all permutations to get optimal
      TC(j) = Inf;
      for k = 1:size(Rj,1)
         [~,TCj] = insertimprove(Rj(k,:),rTCh,sh);
         if TCj < TC(j), TC(j) = TCj; end
      end
   end
   C(i,:) = TC;
   TC = diff([0 TC]);
   C(i,:) = TC(invperm(R(i,:)));
end
mdisp(C,sum(R.*repmat(10.^[n-1:-1:0],size(R,1),1),2))
%% Equal charge allocation
TCc = min(sum(C,2))
c_equal = repmat(TCc/n,1,n)
pct_reduct = round(100*(1 - c_equal./c0))
%% Equal savings allocation
Sn = sum(c0) - TCc
c_eq_sav = c0 - Sn/n
pct_reduct = round(100*(1 - c_eq_sav./c0))
%% Exact Shapley allocation
c_Shap_exact = mean(C,1)
pct_reduct = round(100*(1 - c_Shap_exact./c0))
%% Pairwise approximate Shapely allocation
[~,S2] = pairwisesavings(rTCh,sh)
c_Shap_approx = c0 - (Sn/n + sum(S2)/(n-1) - sum(sum(S2))/(n*(n-1)))
pct_reduct = round(100*(1 - c_Shap_approx./c0))
%% Comparison
vdisp('c0,c_equal,c_eq_sav,c_Shap_exact,c_Shap_approx',true,true)
%% Add 4th shipment (exact and approx Shapley allocation differ)
sh(4).b = 5; sh(4).e = 4; sh(4).d = D(5,4);
sdisp(sh,1)
rTCh = @(rte) rteTC(rte,sh,D*r);
n = length(sh)
