% Freight Transport 1: One-Time Truck Shipments

%% Truck Shipment Example: One-Time
%% Question 1
sh.d = 532;
uwt = 40;
ucu = 9;
sh.s = uwt/ucu
tr.Kwt = 25; tr.Kcu = 2750;
qmax = min(tr.Kwt,sh.s*tr.Kcu/2000)
qmax = maxpayld(sh,tr)
%% Question 2
ud = 350
q = ud*(uwt/2000)
ceil(q/qmax)
%% Question 3
ppiTL = 131.4; % Jan 2018 (P)
tr.r = 2 * (ppiTL/102.7)
cTL = ceil(q/qmax) * tr.r * sh.d
cTL = transcharge(q,sh,tr)
%% Question 4
qTL = qmax*floor(q/qmax)
qLTL = q - qmax*floor(q/qmax)
ppiLTL = 179.4; % Jan 2018 (P)
cLTL = transcharge(qLTL,sh,[],ppiLTL)
rLTL = rateLTL(qLTL,sh.s,sh.d,ppiLTL)
cLTL = rLTL * sh.d * qLTL
%% Question 5
c_comb = transcharge(qTL,sh,tr) + cLTL
cTL - c_comb
%% Question 6
cTLh = @(q) ceil(q/qmax) * tr.r * sh.d;
rLTLh = @(q) rateLTL(q,sh.s,sh.d,ppiLTL);
cLTLh = @(q) rLTLh(q) * sh.d * q;
qI = fminsearch(@(q) abs(cTLh(q)-cLTLh(q)),qLTL)
%% Question 7
MC_TL = mincharge(sh.d,ppiTL)
MC_LTL = mincharge(sh.d,[],ppiLTL)
%% Independent shipment charge
c0h = @(q) transcharge(q,sh,tr,ppiLTL);
fplot(c0h,[0 1.2*qmax]), shg
title('Independent shipment charge: Class 200 from 27606 to 32606')
ylabel('Transport Charge ($)')
xlabel('Shipment Size (ton)')
hold on, plot(qI,c0h(qI),'ro'), shg
plot(qmax,c0h(qmax),'co'), shg, hold off
c0h(0)
c0h(1/2000)
%% Question 8
qLTL_LB = round(2000*qLTL)
%% Question 9
q = qLTL; class = 200; disc = 0; MC = 95.23;
qB = [0 0.25 0.5 1 2.5 5 10 15 20 Inf];
i = find(qB(1:end-1) <= q & q < qB(2:end))
ODi = 99.92
ci = ODi*20*q
ODiplus1 = 81.89
qBi = qB(i+1)
ciplus1 = ODiplus1*20*qBi
c_tar = (1 - disc)*max(MC,min(ci,ciplus1))
%% Question 10
implied_disc = (c_tar - cLTL)/c_tar
weight_break = ODiplus1*qBi/ODi
qLTL
