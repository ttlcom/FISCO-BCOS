/*
    This file is part of cpp-ethereum.

    cpp-ethereum is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    cpp-ethereum is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with cpp-ethereum.  If not, see <http://www.gnu.org/licenses/>.
*/
/**
 * @file: Raft.h
 * @author: fisco-dev
 *
 * @date: 2017
 * A proof of work algorithm.
 */
#pragma once

#include "Common.h"
#include <libblockchain/BlockChainInterface.h>
#include <libblockverifier/BlockVerifierInterface.h>
#include <libconsensus/ConsensusEngineBase.h>
#include <libethcore/Block.h>
#include <libnetwork/Common.h>
#include <libp2p/P2PInterface.h>
#include <libp2p/P2PMessage.h>
#include <libp2p/P2PSession.h>
#include <libstorage/Storage.h>
#include <libsync/SyncInterface.h>
#include <libtxpool/TxPoolInterface.h>

#include <memory>

namespace dev
{
namespace consensus
{
DEV_SIMPLE_EXCEPTION(RaftEngineInitFailed);
DEV_SIMPLE_EXCEPTION(RaftEngineUnexpectError);

class RaftEngine : public ConsensusEngineBase
{
public:
    RaftEngine(std::shared_ptr<dev::p2p::P2PInterface> _service,
        std::shared_ptr<dev::txpool::TxPoolInterface> _txPool,
        std::shared_ptr<dev::blockchain::BlockChainInterface> _blockChain,
        std::shared_ptr<dev::sync::SyncInterface> _blockSync,
        std::shared_ptr<dev::blockverifier::BlockVerifierInterface> _blockVerifier,
        KeyPair const& _keyPair, unsigned _minElectTime, unsigned _maxElectTime,
        dev::PROTOCOL_ID const& _protocolId, dev::h512s const& _minerList = dev::h512s())
      : ConsensusEngineBase(
            _service, _txPool, _blockChain, _blockSync, _blockVerifier, _protocolId, _minerList),
        m_keyPair(_keyPair),
        m_minElectTimeout(_minElectTime),
        m_maxElectTimeout(_maxElectTime)
    {
        m_service->registerHandlerByProtoclID(
            m_protocolId, boost::bind(&RaftEngine::onRecvRaftMessage, this, _1, _2, _3));
    }

    dev::u256 getNodeIdx() const
    {
        RecursiveGuard recursiveGuard(m_mutex);
        return m_nodeIdx;
    }

    dev::u256 getTerm() const
    {
        RecursiveGuard recursiveGuard(m_mutex);
        return m_term;
    }

    dev::eth::BlockHeader getHighestBlockHeader() const
    {
        RecursiveGuard recursiveGuard(m_mutex);
        return m_highestBlockHeader;
    }

    dev::u256 getLastLeaderTerm() const
    {
        RecursiveGuard recursiveGuard(m_mutex);
        return m_lastLeaderTerm;
    }

    void setStorage(dev::storage::Storage::Ptr storage)
    {
        RecursiveGuard recursiveGuard(m_mutex);
        m_storage = storage;
    }

    void start() override;
    void reportBlock(dev::eth::Block const& _block) override;
    bool shouldSeal();
    bool commit(dev::eth::Block const& _block);
    bool reachBlockIntervalTime();


protected:
    void initRaftEnv();
    void onRecvRaftMessage(dev::p2p::NetworkException _exception,
        dev::p2p::P2PSession::Ptr _session, dev::p2p::P2PMessage::Ptr _message);
    bool isValidReq(dev::p2p::P2PMessage::Ptr _message, dev::p2p::P2PSession::Ptr _session,
        ssize_t& _peerIndex) override;

    bool checkElectTimeout();
    void resetElectTimeout();

    void switchToCandidate();
    void switchToFollower(u256 const& _leader);
    void switchToLeader();

    bool wonElection(u256 const& _votes) { return _votes >= m_nodeNum - m_f; }
    bool isMajorityVote(u256 const& _votes) { return _votes >= m_nodeNum - m_f; }

    dev::p2p::P2PMessage::Ptr generateVoteReq();
    dev::p2p::P2PMessage::Ptr generateHeartbeat();

    void broadcastVoteReq();
    void broadcastHeartbeat();
    void broadcastMsg(dev::p2p::P2PMessage::Ptr _data);

    // handle response 处理响应消息
    bool handleVoteRequest(u256 const& _from, h512 const& _node, RaftVoteReq const& _req);
    HandleVoteResult handleVoteResponse(
        u256 const& _from, h512 const& _node, RaftVoteResp const& _req, VoteState& vote);
    bool handleHeartBeat(u256 const& _from, h512 const& _node, RaftHeartBeat const& _hb);
    bool sendResponse(
        u256 const& _to, h512 const& _node, RaftPacketType _packetType, RaftMsg const& _resp);

    void workLoop() override;
    void resetConfig() override;
    void updateMinerList();

    void runAsLeader();
    void runAsFollower();
    void runAsCandidate();

    bool checkHeartBeatTimeout();
    ssize_t getIndexByMiner(dev::h512 const& _nodeId);
    bool getNodeIdByIndex(h512& _nodeId, const u256& _nodeIdx) const;
    dev::p2p::P2PMessage::Ptr transDataToMessage(
        bytesConstRef data, RaftPacketType const& packetType, PROTOCOL_ID const& protocolId);

    unsigned getState()
    {
        RecursiveGuard l(m_mutex);
        return m_state;
    }

    void setLeader(u256 const& _leader)
    {
        RecursiveGuard l(m_mutex);
        m_leader = _leader;
    }

    void setVote(u256 const& _candidate)
    {
        RecursiveGuard l(m_mutex);
        m_vote = _candidate;
    }

    void increaseElectTime();
    void recoverElectTime();
    void clearFirstVoteCache();

    void execBlock(Sealing& _sealing, dev::eth::Block const& _block);
    void checkBlockValid(dev::eth::Block const& _block);
    void checkMinerList(dev::eth::Block const& _block);
    void checkAndSave(Sealing& _sealing);

    mutable RecursiveMutex m_mutex;
    dev::KeyPair m_keyPair;

    unsigned m_electTimeout;
    unsigned m_minElectTimeout;
    unsigned m_maxElectTimeout;
    unsigned m_minElectTimeoutInit;
    unsigned m_maxElectTimeoutInit;
    unsigned m_minElectTimeoutBoundary;
    unsigned m_maxElectTimeoutBoundary;
    std::chrono::system_clock::time_point m_lastElectTime;

    static unsigned const s_heartBeatIntervalRatio = 4;
    unsigned m_heartbeatTimeout;
    unsigned m_heartbeatInterval;
    unsigned m_heartbeatCount = 0;
    std::chrono::system_clock::time_point m_lastHeartbeatTime;
    std::chrono::system_clock::time_point m_lastHeartbeatReset;

    unsigned m_increaseTime;

    // header of highest block
    dev::eth::BlockHeader m_highestBlockHeader;
    // message queue, defined in Common.h
    RaftMsgQueue m_msgQueue;
    // role of node
    RaftRole m_state = EN_STATE_FOLLOWER;

    u256 m_firstVote = Invalid256;
    u256 m_term = u256(0);
    u256 m_lastLeaderTerm = u256(0);

    u256 m_leader;
    u256 m_vote;
    u256 m_nodeIdx;

    struct BlockRef
    {
        u256 height;
        h256 block_hash;
        BlockRef() : height(0), block_hash(0) {}
        BlockRef(u256 _height, h256 _hash) : height(_height), block_hash(_hash) {}
    };
    std::unordered_map<h512, BlockRef> m_memberBlock;  // <node_id, BlockRef>
    static const unsigned c_PopWaitSeconds = 5;

    bool m_cfgErr = false;
    dev::storage::Storage::Ptr m_storage;
    // the block number that update the miner list
    int64_t m_lastObtainMinerNum = 0;

    u256 m_lastBlockTime;
};
}  // namespace consensus
}  // namespace dev
