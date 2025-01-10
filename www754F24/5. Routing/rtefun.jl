# Routing Functions

# Cost of each segment in a location vector
segcost(loc, C) = map(i -> C[loc[i], loc[i+1]], 1:length(loc) - 1)

# Two-Opt Route Improvement Procedure
function twoopt(r, rTCh)
    rᵒ, TCᵒ = copy(r), rTCh(r)
    done = false
    while !done
        done = true
        for i = 1:length(r)-2
            for j = i+2:min(length(r)-1, length(r)+i-3)
                r′ = vcat(r[1:i], reverse(r[i+1:j]), r[j+1:end])
                TC = rTCh(r′)
                if TC < TCᵒ
                    rᵒ, TCᵒ = r′, TC
                    done = false
                    break
                end
            end
            if done == false
                break
            end
        end
        r = copy(rᵒ)
    end
    return rᵒ, TCᵒ
end

# True/False if node origin/destination in route
isorigin(rte) = begin
    seen = Set()
    [i ∉ seen ? (push!(seen, i); true) : false for i in rte]
end

# Convert route to location vector
rte2loc(rte, sh, tr = (b = [], e = [])) = 
    vcat(tr.b, ifelse.(isorigin(rte), sh[rte, :b], sh[rte, :e]), tr.e)

# Total route cost
rteTC(rte, sh, C, tr = (b = [], e = [])) = sum(segcost(rte2loc(rte, sh, tr), C))

# Min Cost Shipment Insertion Procedure
function mincostinsert(idx, rte, rteTCh)
    rteᵒ, TCᵒ = copy(rte), Inf
    for i = 1:length(rte)
        for j = max(2,i):length(rte) + 1
            rte′ = vcat(rte[1:i-1], idx, rte[i:j-1], idx, rte[j:end])
            TC = rteTCh(rte′)
            if TC < TCᵒ
                rteᵒ, TCᵒ = rte′, TC
            end
        end
    end
    return rteᵒ, TCᵒ
end

# Savings for all pairs of shipments
function pairwisesavings(rteTCh, sh)
    iᵒ, jᵒ, sᵒ = Int[], Int[], Float64[]
    for i = 1:nrow(sh)-1
        for j = i+1:nrow(sh)
            s = rteTCh([i, i]) + rteTCh([j, j]) - mincostinsert(i, [j, j], rteTCh)[2]
            s > 0 && (push!(iᵒ, i); push!(jᵒ, j); push!(sᵒ, s))
        end
    end
    sidx = sortperm(sᵒ, rev=true)
    return iᵒ[sidx], jᵒ[sidx], sᵒ[sidx]
end

# Savings Route Construction Procedure
function savings(rteTCh, sh)
    TC = nothing
    rte = [[i, i] for i in 1:nrow(sh)]
    inr = [1:nrow(sh);]
    iˢ, jˢ = pairwisesavings(rteTCh, sh)
    for (i, j) in zip(iˢ, jˢ)
        if inr[i] != inr[j]
            # Insert shmt from shorter (src) into longer (tgt) route
            inr_src, inr_tgt = length(rte[inr[i]]) < length(rte[inr[j]]) ?
                (inr[i], inr[j]) : (inr[j], inr[i])
            rte′ = copy(rte[inr_tgt])
            idx_src = unique(rte[inr_src])
            for k in idx_src
                rte′, TC = mincostinsert(k, rte′, rteTCh)
                if isinf(TC)
                    break
                end
            end
            if !isinf(TC)
                rte[inr_tgt] = rte′
                inr[idx_src] .= inr_tgt
                rte[inr_src] = []
            end
        end
    end
    return filter!(!isempty, rte)
end
