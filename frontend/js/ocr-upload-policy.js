const OcrUploadPolicy = (() => {
    const MINIMUM_CONFIDENCE = 0.95;
    const MAX_REUPLOADS = 3;

    function startRound() {
        return { reuploads: 0 };
    }

    function isAccepted(confidence) {
        return Number.isFinite(confidence) && confidence >= MINIMUM_CONFIDENCE;
    }

    function lowConfidenceState(round) {
        const remainingReuploads = Math.max(MAX_REUPLOADS - round.reuploads, 0);
        return {
            canRetry: remainingReuploads > 0,
            remainingReuploads,
        };
    }

    function beginReupload(round) {
        if (!lowConfidenceState(round).canRetry) {
            return false;
        }
        round.reuploads += 1;
        return true;
    }

    return Object.freeze({
        MINIMUM_CONFIDENCE,
        MAX_REUPLOADS,
        startRound,
        isAccepted,
        lowConfidenceState,
        beginReupload,
    });
})();

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { OcrUploadPolicy };
}
